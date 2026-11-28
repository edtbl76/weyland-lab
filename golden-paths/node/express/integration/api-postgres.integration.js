// Express's own integration test (B262): its HTTP API with REAL Postgres behind it. The framework-neutral adapter
// tests are items-backends.integration.js (a synced copy, shared by every Node path); this file is the one part that
// is Express's: the wiring from routes through the createApp({store}) factory to the Postgres store.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const request = require('supertest');
const { createApp } = require('../src/app');
const { loadSettings } = require('../src/shared/settings');
const { PostgresItemStore } = require('../src/shared/items-backends');

const URL = process.env.GOLDEN_DATABASE_URL;
if (!URL) throw new Error('integration tier: GOLDEN_DATABASE_URL is not set; refusing to run');

async function appOnPostgres() {
  const app = createApp({ settings: loadSettings({ GOLDEN_GREETING: 'hi' }), store: new PostgresItemStore(URL), log: () => {} });
  await app.locals.lifecycle.start();
  return app;
}

// The CI Postgres is shared by every path's tests, so the item can be on any page: walk them (limit max 100).
async function listed(app, id) {
  for (let offset = 0; ; offset += 100) {
    const { items } = (await request(app).get(`/items?limit=100&offset=${offset}`).expect(200)).body;
    if (items.some((i) => i.id === id)) return true;
    if (items.length < 100) return false;
  }
}

test('the HTTP API runs on Postgres and survives a restart', async () => {
  const app = await appOnPostgres();
  let made;
  try {
    made = (await request(app).post('/items').send({ name: 'express-pg', tags: ['x'] }).expect(201)).body;
    assert.deepEqual((await request(app).get(`/items/${made.id}`)).body, made);
    assert.ok(await listed(app, made.id), `item ${made.id} is not in any page of GET /items`);
    assert.equal((await request(app).get('/items/999999999')).body.error.code, 'not_found');
  } finally {
    await app.locals.lifecycle.stop();
  }
  const again = await appOnPostgres();                    // a new process's view: it was stored
  try {
    assert.deepEqual((await request(again).get(`/items/${made.id}`)).body, made);
  } finally {
    await again.locals.lifecycle.stop();
  }
});

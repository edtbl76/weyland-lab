// NestJS's own integration test (B262): its HTTP API with REAL Postgres behind it. The framework-neutral adapter tests
// are items-backends.integration.js (a synced copy, shared by every Node path); this file is the one part that is
// Nest's: the wiring from controllers through the ITEM_STORE provider to the Postgres store. It loads the compiled
// app (dist/, built by the integration-node step first: `npm run build`), plain JavaScript like the shared tests.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const request = require('supertest');
const { createApp } = require('../dist/bootstrap');
const { Lifecycle } = require('../dist/lifecycle');
const { loadSettings } = require('../dist/shared/settings');
const { PostgresItemStore } = require('../dist/shared/items-backends');

const URL = process.env.GOLDEN_DATABASE_URL;
if (!URL) throw new Error('integration tier: GOLDEN_DATABASE_URL is not set; refusing to run');

async function appOnPostgres() {
  const app = await createApp({ settings: loadSettings({ GOLDEN_GREETING: 'hi' }), store: new PostgresItemStore(URL), log: () => {} });
  await app.get(Lifecycle).start();
  return app;
}

// The CI Postgres is shared by every path's tests, so the item can be on any page: walk them (limit max 100).
async function listed(server, id) {
  for (let offset = 0; ; offset += 100) {
    const { items } = (await request(server).get(`/items?limit=100&offset=${offset}`).expect(200)).body;
    if (items.some((i) => i.id === id)) return true;
    if (items.length < 100) return false;
  }
}

test('the HTTP API runs on Postgres and survives a restart', async () => {
  const app = await appOnPostgres();
  let made;
  try {
    const server = app.getHttpServer();
    made = (await request(server).post('/items').send({ name: 'nestjs-pg', tags: ['x'] }).expect(201)).body;
    assert.deepEqual((await request(server).get(`/items/${made.id}`)).body, made);
    assert.ok(await listed(server, made.id), `item ${made.id} is not in any page of GET /items`);
    assert.equal((await request(server).get('/items/999999999')).body.error.code, 'not_found');
  } finally {
    await app.close();                                    // OnApplicationShutdown closes the store
  }
  const again = await appOnPostgres();                    // a new process's view: it was stored
  try {
    assert.deepEqual((await request(again.getHttpServer()).get(`/items/${made.id}`)).body, made);
  } finally {
    await again.close();
  }
});

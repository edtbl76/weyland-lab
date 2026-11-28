// Fastify's own integration test (B262): its HTTP API with REAL Postgres behind it. The framework-neutral adapter
// tests are items-backends.integration.js (a synced copy, shared by every Node path); this file is the one part that
// is Fastify's: the wiring from routes through the store decorator to the Postgres store, via app.inject().
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { build } = require('../src/app');
const { loadSettings } = require('../src/shared/settings');
const { PostgresItemStore } = require('../src/shared/items-backends');

const URL = process.env.GOLDEN_DATABASE_URL;
if (!URL) throw new Error('integration tier: GOLDEN_DATABASE_URL is not set; refusing to run');

async function appOnPostgres() {
  const app = build({ settings: loadSettings({ GOLDEN_GREETING: 'hi' }), store: new PostgresItemStore(URL), log: () => {} });
  await app.lifecycle.start();
  return app;
}

// The CI Postgres is shared by every path's tests, so the item can be on any page: walk them (limit max 100).
async function listed(app, id) {
  for (let offset = 0; ; offset += 100) {
    const res = await app.inject({ method: 'GET', url: `/items?limit=100&offset=${offset}` });
    assert.equal(res.statusCode, 200);
    const { items } = res.json();
    if (items.some((i) => i.id === id)) return true;
    if (items.length < 100) return false;
  }
}

test('the HTTP API runs on Postgres and survives a restart', async () => {
  const app = await appOnPostgres();
  let made;
  try {
    const res = await app.inject({ method: 'POST', url: '/items', payload: { name: 'fastify-pg', tags: ['x'] } });
    assert.equal(res.statusCode, 201);
    made = res.json();
    assert.deepEqual((await app.inject({ method: 'GET', url: `/items/${made.id}` })).json(), made);
    assert.ok(await listed(app, made.id), `item ${made.id} is not in any page of GET /items`);
    assert.equal((await app.inject({ method: 'GET', url: '/items/999999999' })).json().error.code, 'not_found');
  } finally {
    await app.close();                                    // onClose closes the store
  }
  const again = await appOnPostgres();                    // a new process's view: it was stored
  try {
    assert.deepEqual((await again.inject({ method: 'GET', url: `/items/${made.id}` })).json(), made);
  } finally {
    await again.close();
  }
});

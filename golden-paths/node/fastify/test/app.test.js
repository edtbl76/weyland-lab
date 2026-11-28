// Contract self-test (Fastify): the minimal contract and deep contract v2 (C1-C9), one test per row, via
// app.inject() (no port), plus serve() on an ephemeral port for the drain. C11 is test/tracing.test.js.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { build, serve, SERVICE_NAME } = require('../src/app');
const { loadSettings } = require('../src/shared/settings');
const { InMemoryItemStore } = require('../src/shared/items-store');

const quiet = () => {};

async function started(t, opts = {}) {
  const app = build({ log: quiet, ...opts });
  await app.lifecycle.start();
  t.after(() => app.close());
  return app;
}
const get = (app, url, headers) => app.inject({ method: 'GET', url, headers });
const post = (app, url, payload) => app.inject({ method: 'POST', url, payload });

// ── the minimal contract ──────────────────────────────────────────────────────────────────────────────────────────
test('health is ok', async (t) => {
  const res = await get(await started(t), '/health');
  assert.equal(res.statusCode, 200);
  assert.equal(res.json().status, 'ok');
});

test('hello returns the known payload', async (t) => {
  const res = await get(await started(t), '/hello');
  assert.deepEqual(res.json(), { service: SERVICE_NAME, message: 'hello, weyland' });
});

test('metrics exposes prometheus', async (t) => {
  const app = await started(t);
  await get(app, '/hello');
  const res = await get(app, '/metrics');
  assert.equal(res.statusCode, 200);
  assert.ok(res.body.includes('golden_hello_requests_total'));
});

// ── C1 routing ────────────────────────────────────────────────────────────────────────────────────────────────────
test('C1: create, get and list items', async (t) => {
  const app = await started(t);
  const made = await post(app, '/items', { name: 'widget', tags: ['a'] });
  assert.equal(made.statusCode, 201);
  assert.deepEqual(made.json(), { id: 1, name: 'widget', tags: ['a'] });
  assert.deepEqual((await get(app, '/items/1')).json(), made.json());
  assert.deepEqual((await get(app, '/items')).json(), { items: [made.json()], limit: 20, offset: 0 });
});

test('C1: limit and offset page the list', async (t) => {
  const app = await started(t);
  for (const name of ['a', 'b', 'c']) await post(app, '/items', { name });
  const page = (await get(app, '/items?limit=1&offset=1')).json();
  assert.deepEqual(page.items.map((i) => i.name), ['b']);
  assert.deepEqual([page.limit, page.offset], [1, 1]);
});

// ── C2 validation (JSON Schema) ───────────────────────────────────────────────────────────────────────────────────
for (const [body, field] of [
  [{ name: '' }, 'name'], [{ name: 'x'.repeat(65) }, 'name'], [{ tags: [] }, 'name'],
  [{ name: 'ok', tags: ['1', '2', '3', '4', '5', '6'] }, 'tags'], [{ name: 'ok', tags: 'not-a-list' }, 'tags'],
]) {
  test(`C2: an invalid body ${JSON.stringify(body)} is 422 naming the field`, async (t) => {
    const res = await post(await started(t), '/items', body);
    assert.equal(res.statusCode, 422);
    assert.equal(res.json().error.code, 'validation_failed');
    assert.ok(res.json().error.fields.map((f) => f.field).includes(field), JSON.stringify(res.json()));
  });
}

for (const [query, field] of [['limit=0', 'limit'], ['limit=101', 'limit'], ['offset=-1', 'offset'], ['limit=x', 'limit']]) {
  test(`C2: an invalid query ${query} is 422`, async (t) => {
    const res = await get(await started(t), `/items?${query}`);
    assert.equal(res.statusCode, 422);
    assert.ok(res.json().error.fields.map((f) => f.field).includes(field), JSON.stringify(res.json()));
  });
}

test('C2: a non-integer id is 422', async (t) => {
  const res = await get(await started(t), '/items/abc');
  assert.equal(res.statusCode, 422);
  assert.equal(res.json().error.fields[0].field, 'id');
});

test('C2: malformed JSON is 422, not a framework error page', async (t) => {
  const res = await (await started(t)).inject({
    method: 'POST', url: '/items', payload: '{"name":', headers: { 'content-type': 'application/json' },
  });
  assert.equal(res.statusCode, 422);
  assert.equal(res.json().error.code, 'validation_failed');
});

// ── C3 structured errors ──────────────────────────────────────────────────────────────────────────────────────────
test('C3: an unknown id is a 404 envelope carrying the request id', async (t) => {
  const res = await get(await started(t), '/items/999', { 'x-request-id': 'rid-404' });
  assert.equal(res.statusCode, 404);
  assert.deepEqual(res.json(), { error: { code: 'not_found', message: 'item 999 not found', request_id: 'rid-404' } });
});

test('C3: an unknown route is a 404 envelope', async (t) => {
  const res = await get(await started(t), '/nope');
  assert.equal(res.statusCode, 404);
  assert.equal(res.json().error.code, 'not_found');
});

test('C3: an unhandled exception is a 500 envelope that hides the detail', async (t) => {
  const logged = [];
  const app = await started(t, {
    log: (line) => logged.push(line),
    extraRoutes: (a) => a.get('/boom', async () => { throw new Error('secret detail'); }),
  });
  const res = await get(app, '/boom');
  assert.equal(res.statusCode, 500);
  assert.equal(res.json().error.code, 'internal');
  assert.equal(res.json().error.message, 'internal error');
  assert.ok(!res.body.includes('secret detail'));
  assert.ok(logged.join('\n').includes('secret detail'));    // the detail goes to the log, never to the client
});

// ── C4 middleware (hooks) ─────────────────────────────────────────────────────────────────────────────────────────
test('C4: X-Request-ID is echoed when sent', async (t) => {
  const res = await get(await started(t), '/health', { 'x-request-id': 'abc-123' });
  assert.equal(res.headers['x-request-id'], 'abc-123');
});

test('C4: X-Request-ID is generated when absent', async (t) => {
  const res = await get(await started(t), '/health');
  assert.match(res.headers['x-request-id'], /^[0-9a-f]{32}$/);
});

test('C4: one JSON access-log line per request', async (t) => {
  const logged = [];
  const app = await started(t, { log: (line) => logged.push(line) });
  await get(app, '/items/42', { 'x-request-id': 'log-rid' });
  const lines = logged.map((l) => JSON.parse(l)).filter((l) => l.path === '/items/42');
  assert.equal(lines.length, 1);
  assert.equal(lines[0].method, 'GET');
  assert.equal(lines[0].status, 404);
  assert.equal(lines[0].request_id, 'log-rid');
  assert.equal(typeof lines[0].duration_ms, 'number');
});

// ── C5 metrics ────────────────────────────────────────────────────────────────────────────────────────────────────
test('C5: per-route request counter and latency histogram, by route template', async (t) => {
  const app = await started(t);
  await get(app, '/items/12345');
  const text = (await get(app, '/metrics')).body;
  assert.match(text, /http_requests_total\{route="\/items\/:id",status="404"\} [1-9]/);
  assert.ok(text.includes('http_request_duration_seconds_bucket{le='));
  assert.ok(!text.includes('route="/items/12345"'));          // the template, never the raw path
});

// ── C6 config ─────────────────────────────────────────────────────────────────────────────────────────────────────
test('C6: GOLDEN_GREETING shapes /hello', async (t) => {
  const app = await started(t, { settings: loadSettings({ GOLDEN_GREETING: 'hi there' }) });
  assert.equal((await get(app, '/hello')).json().message, 'hi there');
});

test('C6: an empty greeting fails startup with a clear message', () => {
  assert.throws(() => loadSettings({ GOLDEN_GREETING: '  ' }), /GOLDEN_GREETING must not be empty/);
  const saved = process.env.GOLDEN_GREETING;
  process.env.GOLDEN_GREETING = '';
  try {
    assert.throws(() => build({ log: quiet }), /GOLDEN_GREETING/);   // build() reads and validates the env
  } finally {
    if (saved === undefined) delete process.env.GOLDEN_GREETING; else process.env.GOLDEN_GREETING = saved;
  }
});

// ── C7 DI (decorator) ─────────────────────────────────────────────────────────────────────────────────────────────
test('C7: the injected store serves the routes, decorated onto the instance', async (t) => {
  const store = new InMemoryItemStore();
  await store.create('pre-seeded', ['di']);
  const app = await started(t, { store });
  assert.equal(app.store, store);
  assert.equal((await get(app, '/items/1')).json().name, 'pre-seeded');
});

// ── C8 lifecycle ──────────────────────────────────────────────────────────────────────────────────────────────────
test('C8: /ready is 503 until the store is open, then 200; close (onClose) closes the store', async () => {
  const store = new InMemoryItemStore();
  const app = build({ store, log: quiet });
  const before = await get(app, '/ready');
  assert.equal(before.statusCode, 503);
  assert.equal(before.json().error.code, 'not_ready');
  await app.lifecycle.start();
  assert.equal((await get(app, '/ready')).statusCode, 200);
  await app.close();
  assert.equal(store.closed, true);
});

test('C8: shutdown drains an in-flight request before the store closes', async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const store = new InMemoryItemStore();
  const app = build({ store, log: quiet, extraRoutes: (a) => a.get('/slow', async () => { await gate; return { done: true }; }) });
  const { port, shutdown } = await serve(app, { port: 0, host: '127.0.0.1' });
  const inFlight = fetch(`http://127.0.0.1:${port}/slow`);
  await new Promise((r) => setTimeout(r, 50));            // the request is now in the handler
  const stopping = shutdown();
  release();
  const res = await inFlight;
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { done: true });
  await stopping;
  assert.equal(store.closed, true);
});

// C10 (OpenAPI) is skipped for Fastify: no native document without a plugin (docs/concepts/golden-path-capabilities.md).

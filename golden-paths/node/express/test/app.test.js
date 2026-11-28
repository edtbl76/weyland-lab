// Contract self-test (Express): the minimal contract and deep contract v2 (C1-C11), one test per row, over supertest
// against createApp() (no port), plus serve() on an ephemeral port for the lifecycle and tracing rows.
'use strict';

const request = require('supertest');
const { createApp, serve, SERVICE_NAME } = require('../src/app');
const { loadSettings } = require('../src/shared/settings');
const { InMemoryItemStore } = require('../src/shared/items-store');

const quiet = () => {};                                  // the access log, silenced unless a test reads it

async function started(opts = {}) {
  const app = createApp({ log: quiet, ...opts });
  await app.locals.lifecycle.start();
  return app;
}

// ── the minimal contract ──────────────────────────────────────────────────────────────────────────────────────────
test('health is ok', async () => {
  const res = await request(await started()).get('/health');
  expect(res.status).toBe(200);
  expect(res.body.status).toBe('ok');
});

test('hello returns the known payload', async () => {
  const res = await request(await started()).get('/hello');
  expect(res.status).toBe(200);
  expect(res.body).toEqual({ service: SERVICE_NAME, message: 'hello, weyland' });
});

test('metrics exposes prometheus', async () => {
  const app = await started();
  await request(app).get('/hello');
  const res = await request(app).get('/metrics');
  expect(res.status).toBe(200);
  expect(res.text).toContain('golden_hello_requests_total');
});

// ── C1 routing ────────────────────────────────────────────────────────────────────────────────────────────────────
test('C1: create, get and list items', async () => {
  const app = await started();
  const made = await request(app).post('/items').send({ name: 'widget', tags: ['a'] });
  expect(made.status).toBe(201);
  expect(made.body).toEqual({ id: 1, name: 'widget', tags: ['a'] });
  expect((await request(app).get('/items/1')).body).toEqual(made.body);
  const page = await request(app).get('/items');
  expect(page.body).toEqual({ items: [made.body], limit: 20, offset: 0 });
});

test('C1: limit and offset page the list', async () => {
  const app = await started();
  for (const name of ['a', 'b', 'c']) await request(app).post('/items').send({ name });
  const page = await request(app).get('/items?limit=1&offset=1');
  expect(page.body.items.map((i) => i.name)).toEqual(['b']);
  expect([page.body.limit, page.body.offset]).toEqual([1, 1]);
});

// ── C2 validation ─────────────────────────────────────────────────────────────────────────────────────────────────
test.each([
  [{ name: '' }, 'name'],
  [{ name: 'x'.repeat(65) }, 'name'],
  [{ tags: [] }, 'name'],
  [{ name: 'ok', tags: ['1', '2', '3', '4', '5', '6'] }, 'tags'],
  [{ name: 'ok', tags: [1] }, 'tags'],
])('C2: an invalid body %j is 422 naming the field', async (body, field) => {
  const res = await request(await started()).post('/items').send(body);
  expect(res.status).toBe(422);
  expect(res.body.error.code).toBe('validation_failed');
  expect(res.body.error.fields.map((f) => f.field)).toContain(field);
});

test.each([['limit=0', 'limit'], ['limit=101', 'limit'], ['offset=-1', 'offset'], ['limit=x', 'limit']])(
  'C2: an invalid query %s is 422', async (query, field) => {
    const res = await request(await started()).get(`/items?${query}`);
    expect(res.status).toBe(422);
    expect(res.body.error.fields.map((f) => f.field)).toContain(field);
  });

test('C2: a non-integer id is 422', async () => {
  const res = await request(await started()).get('/items/abc');
  expect(res.status).toBe(422);
  expect(res.body.error.fields[0].field).toBe('id');
});

test('C2: malformed JSON is 422, not a framework error page', async () => {
  const res = await request(await started()).post('/items').set('Content-Type', 'application/json').send('{"name":');
  expect(res.status).toBe(422);
  expect(res.body.error.code).toBe('validation_failed');
});

// ── C3 structured errors ──────────────────────────────────────────────────────────────────────────────────────────
test('C3: an unknown id is a 404 envelope carrying the request id', async () => {
  const res = await request(await started()).get('/items/999').set('X-Request-ID', 'rid-404');
  expect(res.status).toBe(404);
  expect(res.body).toEqual({ error: { code: 'not_found', message: 'item 999 not found', request_id: 'rid-404' } });
});

test('C3: an unknown route is a 404 envelope', async () => {
  const res = await request(await started()).get('/nope');
  expect(res.status).toBe(404);
  expect(res.body.error.code).toBe('not_found');
});

test('C3: an unhandled exception is a 500 envelope that hides the detail', async () => {
  const logged = [];
  const app = await started({
    log: (line) => logged.push(line),
    extraRoutes: (a) => a.get('/boom', () => { throw new Error('secret detail'); }),
  });
  const res = await request(app).get('/boom');
  expect(res.status).toBe(500);
  expect(res.body.error).toMatchObject({ code: 'internal', message: 'internal error' });
  expect(JSON.stringify(res.body)).not.toContain('secret detail');
  expect(logged.join('\n')).toContain('secret detail');   // the detail goes to the log, never to the client
});

// ── C4 middleware ─────────────────────────────────────────────────────────────────────────────────────────────────
test('C4: X-Request-ID is echoed when sent', async () => {
  const res = await request(await started()).get('/health').set('X-Request-ID', 'abc-123');
  expect(res.headers['x-request-id']).toBe('abc-123');
});

test('C4: X-Request-ID is generated when absent', async () => {
  const res = await request(await started()).get('/health');
  expect(res.headers['x-request-id']).toMatch(/^[0-9a-f]{32}$/);
});

test('C4: one JSON access-log line per request', async () => {
  const logged = [];
  const app = await started({ log: (line) => logged.push(line) });
  await request(app).get('/items/42').set('X-Request-ID', 'log-rid');
  const lines = logged.map((l) => JSON.parse(l)).filter((l) => l.path === '/items/42');
  expect(lines).toHaveLength(1);
  expect(lines[0]).toMatchObject({ method: 'GET', path: '/items/42', status: 404, request_id: 'log-rid' });
  expect(typeof lines[0].duration_ms).toBe('number');
});

// ── C5 metrics middleware ─────────────────────────────────────────────────────────────────────────────────────────
test('C5: per-route request counter and latency histogram, by route template', async () => {
  const app = await started();
  await request(app).get('/items/12345');
  const text = (await request(app).get('/metrics')).text;
  expect(text).toMatch(/http_requests_total\{route="\/items\/:id",status="404"\} [1-9]/);
  expect(text).toContain('http_request_duration_seconds_bucket{le=');
  expect(text).not.toContain('route="/items/12345"');        // the template, never the raw path
});

// ── C6 config ─────────────────────────────────────────────────────────────────────────────────────────────────────
test('C6: GOLDEN_GREETING shapes /hello', async () => {
  const app = await started({ settings: loadSettings({ GOLDEN_GREETING: 'hi there' }) });
  expect((await request(app).get('/hello')).body.message).toBe('hi there');
});

test('C6: an empty greeting fails startup with a clear message', () => {
  expect(() => loadSettings({ GOLDEN_GREETING: '  ' })).toThrow('GOLDEN_GREETING must not be empty');
  const saved = process.env.GOLDEN_GREETING;
  process.env.GOLDEN_GREETING = '';
  try {
    expect(() => createApp({ log: quiet })).toThrow('GOLDEN_GREETING');   // createApp reads and validates the env
  } finally {
    if (saved === undefined) delete process.env.GOLDEN_GREETING; else process.env.GOLDEN_GREETING = saved;
  }
});

// ── C7 DI ─────────────────────────────────────────────────────────────────────────────────────────────────────────
test('C7: the injected store serves the routes', async () => {
  const store = new InMemoryItemStore();
  await store.create('pre-seeded', ['di']);
  const app = await started({ store });
  expect((await request(app).get('/items/1')).body.name).toBe('pre-seeded');
});

// ── C8 lifecycle ──────────────────────────────────────────────────────────────────────────────────────────────────
test('C8: /ready is 503 until the store is open, then 200; stop closes the store', async () => {
  const store = new InMemoryItemStore();
  const app = createApp({ store, log: quiet });
  const before = await request(app).get('/ready');
  expect(before.status).toBe(503);
  expect(before.body.error.code).toBe('not_ready');
  await app.locals.lifecycle.start();
  expect((await request(app).get('/ready')).status).toBe(200);
  await app.locals.lifecycle.stop();
  expect(store.closed).toBe(true);
  expect((await request(app).get('/ready')).status).toBe(503);
});

test('C8: shutdown drains an in-flight request before the store closes', async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const store = new InMemoryItemStore();
  const app = createApp({ store, log: quiet, extraRoutes: (a) => a.get('/slow', async (_q, res) => { await gate; res.json({ done: true }); }) });
  const { server, shutdown } = await serve(app, { port: 0, host: '127.0.0.1' });
  const inFlight = fetch(`http://127.0.0.1:${server.address().port}/slow`);
  await new Promise((r) => setTimeout(r, 50));            // the request is now in the handler
  const stopping = shutdown();
  release();
  const res = await inFlight;
  expect(res.status).toBe(200);
  expect(await res.json()).toEqual({ done: true });
  await stopping;
  expect(store.closed).toBe(true);
});

// ── C10 / C11 ─────────────────────────────────────────────────────────────────────────────────────────────────────
// C10 (OpenAPI) is skipped for Express: no native document (docs/concepts/golden-path-capabilities.md).
// C11 tracing lives in tracing.test.js: the http instrumentation must patch Node's http before Express loads.

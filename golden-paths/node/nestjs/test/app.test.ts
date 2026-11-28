// Contract self-test (NestJS): the minimal contract and deep contract v2 (C1-C10), one test per row, via
// @nestjs/testing's app + supertest against the in-memory HTTP server. C11 is test/tracing.test.ts. Named *.test.ts
// (not *.spec.ts) so the CI lane's *.test.ts discovery glob finds this project's root.
import { INestApplication, Get, Controller, Module } from '@nestjs/common';
import request from 'supertest';
import { createApp, main, serve } from '../src/bootstrap';
import { SERVICE_NAME } from '../src/app.controller';
import { Lifecycle } from '../src/lifecycle';
import { InMemoryItemStore } from '../src/shared/items-store';
import { loadSettings } from '../src/shared/settings';
import type { AppOptions } from '../src/app.module';

const quiet = () => undefined;
const apps: INestApplication[] = [];

async function started(opts: AppOptions = {}) {
  const app = await createApp({ log: quiet, ...opts });
  await app.get(Lifecycle).start();
  apps.push(app);
  return app.getHttpServer();
}

afterEach(async () => {
  while (apps.length) await apps.pop()!.close();
});

// ── the minimal contract ──────────────────────────────────────────────────────────────────────────────────────────
it('health is ok', async () => {
  const res = await request(await started()).get('/health');
  expect(res.status).toBe(200);
  expect(res.body.status).toBe('ok');
});

it('hello returns the known payload', async () => {
  const res = await request(await started()).get('/hello');
  expect(res.body).toEqual({ service: SERVICE_NAME, message: 'hello, weyland' });
});

it('metrics exposes prometheus', async () => {
  const server = await started();
  await request(server).get('/hello');
  const res = await request(server).get('/metrics');
  expect(res.status).toBe(200);
  expect(res.text).toContain('golden_hello_requests_total');
});

// ── C1 routing ────────────────────────────────────────────────────────────────────────────────────────────────────
it('C1: create, get and list items', async () => {
  const server = await started();
  const made = await request(server).post('/items').send({ name: 'widget', tags: ['a'] });
  expect(made.status).toBe(201);
  expect(made.body).toEqual({ id: 1, name: 'widget', tags: ['a'] });
  expect((await request(server).get('/items/1')).body).toEqual(made.body);
  expect((await request(server).get('/items')).body).toEqual({ items: [made.body], limit: 20, offset: 0 });
});

it('C1: limit and offset page the list', async () => {
  const server = await started();
  for (const name of ['a', 'b', 'c']) await request(server).post('/items').send({ name });
  const page = (await request(server).get('/items?limit=1&offset=1')).body;
  expect(page.items.map((i: { name: string }) => i.name)).toEqual(['b']);
  expect([page.limit, page.offset]).toEqual([1, 1]);
});

// ── C2 validation ─────────────────────────────────────────────────────────────────────────────────────────────────
it.each([
  [{ name: '' }, 'name'],
  [{ name: 'x'.repeat(65) }, 'name'],
  [{ tags: [] }, 'name'],
  [{ name: 'ok', tags: ['1', '2', '3', '4', '5', '6'] }, 'tags'],
  [{ name: 'ok', tags: [1] }, 'tags'],
  [{ name: 'ok', tags: 'not-a-list' }, 'tags'],
])('C2: an invalid body %j is 422 naming the field', async (body, field) => {
  const res = await request(await started()).post('/items').send(body);
  expect(res.status).toBe(422);
  expect(res.body.error.code).toBe('validation_failed');
  expect(res.body.error.fields.map((f: { field: string }) => f.field)).toContain(field);
});

it.each([['limit=0', 'limit'], ['limit=101', 'limit'], ['offset=-1', 'offset'], ['limit=x', 'limit']])(
  'C2: an invalid query %s is 422', async (query, field) => {
    const res = await request(await started()).get(`/items?${query}`);
    expect(res.status).toBe(422);
    expect(res.body.error.fields.map((f: { field: string }) => f.field)).toContain(field);
  });

it('C2: a non-integer id is 422', async () => {
  const res = await request(await started()).get('/items/abc');
  expect(res.status).toBe(422);
  expect(res.body.error.fields[0].field).toBe('id');
});

it('C2: malformed JSON is 422, not a framework error page', async () => {
  const res = await request(await started()).post('/items').set('Content-Type', 'application/json').send('{"name":');
  expect(res.status).toBe(422);
  expect(res.body.error.code).toBe('validation_failed');
});

// ── C3 structured errors ──────────────────────────────────────────────────────────────────────────────────────────
it('C3: an unknown id is a 404 envelope carrying the request id', async () => {
  const res = await request(await started()).get('/items/999').set('X-Request-ID', 'rid-404');
  expect(res.status).toBe(404);
  expect(res.body).toEqual({ error: { code: 'not_found', message: 'item 999 not found', request_id: 'rid-404' } });
});

it('C3: an unknown route is a 404 envelope', async () => {
  const res = await request(await started()).get('/nope');
  expect(res.status).toBe(404);
  expect(res.body.error.code).toBe('not_found');
});

it('C3: an unhandled exception is a 500 envelope that hides the detail', async () => {
  @Controller()
  class BoomController {
    @Get('/boom')
    boom() { throw new Error('secret detail'); }
  }
  @Module({ controllers: [BoomController] })
  class BoomModule {}
  const logged: string[] = [];
  const app = await createApp({ log: (l) => logged.push(l), extraModules: [BoomModule] });
  apps.push(app);
  const res = await request(app.getHttpServer()).get('/boom');
  expect(res.status).toBe(500);
  expect(res.body.error).toMatchObject({ code: 'internal', message: 'internal error' });
  expect(JSON.stringify(res.body)).not.toContain('secret detail');
  expect(logged.join('\n')).toContain('secret detail');   // the detail goes to the log, never to the client
});

// ── C4 middleware ─────────────────────────────────────────────────────────────────────────────────────────────────
it('C4: X-Request-ID is echoed when sent', async () => {
  const res = await request(await started()).get('/health').set('X-Request-ID', 'abc-123');
  expect(res.headers['x-request-id']).toBe('abc-123');
});

it('C4: X-Request-ID is generated when absent', async () => {
  const res = await request(await started()).get('/health');
  expect(res.headers['x-request-id']).toMatch(/^[0-9a-f]{32}$/);
});

it('C4: one JSON access-log line per request', async () => {
  const logged: string[] = [];
  const server = await started({ log: (l) => logged.push(l) });
  await request(server).get('/items/42').set('X-Request-ID', 'log-rid');
  const lines = logged.map((l) => JSON.parse(l)).filter((l) => l.path === '/items/42');
  expect(lines).toHaveLength(1);
  expect(lines[0]).toMatchObject({ method: 'GET', path: '/items/42', status: 404, request_id: 'log-rid' });
  expect(typeof lines[0].duration_ms).toBe('number');
});

// ── C5 metrics ────────────────────────────────────────────────────────────────────────────────────────────────────
it('C5: per-route request counter and latency histogram, by route template', async () => {
  const server = await started();
  await request(server).get('/items/12345');
  const text = (await request(server).get('/metrics')).text;
  expect(text).toMatch(/http_requests_total\{route="\/items\/:id",status="404"\} [1-9]/);
  expect(text).toContain('http_request_duration_seconds_bucket{le=');
  expect(text).not.toContain('route="/items/12345"');        // the template, never the raw path
});

// ── C6 config ─────────────────────────────────────────────────────────────────────────────────────────────────────
it('C6: GOLDEN_GREETING shapes /hello', async () => {
  const server = await started({ settings: loadSettings({ GOLDEN_GREETING: 'hi there' }) });
  expect((await request(server).get('/hello')).body.message).toBe('hi there');
});

it('C6: an empty greeting fails startup with a clear message', async () => {
  expect(() => loadSettings({ GOLDEN_GREETING: '  ' })).toThrow('GOLDEN_GREETING must not be empty');
  const saved = process.env.GOLDEN_GREETING;
  process.env.GOLDEN_GREETING = '';
  try {
    await expect(createApp({ log: quiet })).rejects.toThrow('GOLDEN_GREETING');   // the SETTINGS provider validates
  } finally {
    if (saved === undefined) delete process.env.GOLDEN_GREETING; else process.env.GOLDEN_GREETING = saved;
  }
});

// ── C7 DI ─────────────────────────────────────────────────────────────────────────────────────────────────────────
it('C7: the injected store serves the routes', async () => {
  const store = new InMemoryItemStore();
  await store.create('pre-seeded', ['di']);
  const server = await started({ store });
  expect((await request(server).get('/items/1')).body.name).toBe('pre-seeded');
});

// ── C8 lifecycle ──────────────────────────────────────────────────────────────────────────────────────────────────
it('C8: /ready is 503 until the store is open, then 200; close (OnApplicationShutdown) closes the store', async () => {
  const store = new InMemoryItemStore();
  const app = await createApp({ store, log: quiet });
  const before = await request(app.getHttpServer()).get('/ready');
  expect(before.status).toBe(503);
  expect(before.body.error.code).toBe('not_ready');
  await app.get(Lifecycle).start();
  expect((await request(app.getHttpServer()).get('/ready')).status).toBe(200);
  await app.close();
  expect(store.closed).toBe(true);
});

it('C8: shutdown drains an in-flight request before the store closes', async () => {
  let release!: () => void;
  const gate = new Promise<void>((r) => { release = r; });
  @Controller()
  class SlowController {
    @Get('/slow')
    async slow() { await gate; return { done: true }; }
  }
  @Module({ controllers: [SlowController] })
  class SlowModule {}
  const store = new InMemoryItemStore();
  const app = await createApp({ store, log: quiet, extraModules: [SlowModule] });
  const { port, shutdown } = await serve(app, { port: 0, host: '127.0.0.1' });
  const inFlight = fetch(`http://127.0.0.1:${port}/slow`);
  await new Promise((r) => setTimeout(r, 50));            // the request is now in the handler
  const stopping = shutdown();
  release();
  const res = await inFlight;
  expect(res.status).toBe(200);
  expect(await res.json()).toEqual({ done: true });
  await stopping;
  expect(store.closed).toBe(true);
});

it('C8: main() serves on $PORT with the store open, logs its port, and returns its shutdown', async () => {
  const saved = process.env.PORT;
  process.env.PORT = '0';
  const lines: string[] = [];
  const spy = jest.spyOn(console, 'log').mockImplementation((line: string) => { lines.push(line); });
  try {
    const shutdown = await main();
    const started = JSON.parse(lines.find((l) => l.includes('"event":"started"'))!);
    expect(started.service).toBe(SERVICE_NAME);
    expect((await fetch(`http://127.0.0.1:${started.port}/ready`)).status).toBe(200);
    await shutdown();
  } finally {
    spy.mockRestore();
    if (saved === undefined) delete process.env.PORT; else process.env.PORT = saved;
  }
});

// ── C10 OpenAPI ───────────────────────────────────────────────────────────────────────────────────────────────────
it('C10: /openapi.json describes the items API natively', async () => {
  const res = await request(await started()).get('/openapi.json');
  expect(res.status).toBe(200);
  expect(res.body.openapi).toMatch(/^3\./);
  expect(Object.keys(res.body.paths)).toEqual(expect.arrayContaining(['/items', '/items/{id}', '/health', '/hello']));
  expect(res.body.components.schemas.CreateItemDto.required).toEqual(['name']);
});

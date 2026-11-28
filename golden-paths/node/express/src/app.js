// Golden path — Node / Express (B153; deep contract v2 since B262). Runnable, ephemeral, extendable.
//
// The minimal contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Deep contract v2 (docs/concepts/golden-path-capabilities.md), each row in Express's own idiom:
//   C1 routing      GET /items?limit&offset, GET /items/:id, POST /items
//   C2 validation   zod schemas in a validate() middleware; a bad request is 422 with per-field errors
//   C3 errors       one envelope {"error": {code, message, request_id}} from the error middleware (4-arity app.use)
//   C4 middleware   X-Request-ID (echoed or generated) + one JSON access-log line per request, via app.use
//   C5 metrics      http_requests_total{route,status} + http_request_duration_seconds{route}, per route template
//   C6 config       loadSettings(): GOLDEN_GREETING validated when the app is built (empty = refuse to start)
//   C7 DI           Express has none native: createApp({store}) is the factory, in-memory by default
//   C8 lifecycle    lifecycle.start() opens the store and flips /ready; serve()'s shutdown drains (server.close)
//   C9 tests        supertest against createApp(), one test per row (test/app.test.js)
//   C10 OpenAPI     skipped: Express produces no native document
//   C11 tracing     setupTracing() (src/shared/tracing.js), started by server.js before Express loads
//
// Scaffold FROM it: scripts/new-service.sh node/express <your-service>.
'use strict';

const crypto = require('node:crypto');
const express = require('express');
const client = require('prom-client');
const { z } = require('zod');
const { loadSettings } = require('./shared/settings');
const { InMemoryItemStore } = require('./shared/items-store');

// The one place a scaffolded service is renamed (scripts/new-service.sh rewrites this token).
const SERVICE_NAME = 'golden-node-express';

const helloHits = new client.Counter({ name: 'golden_hello_requests_total', help: 'Calls to the demo /hello endpoint' });
const requests = new client.Counter({
  name: 'http_requests_total', help: 'HTTP requests by route template and status', labelNames: ['route', 'status'],
});
const latency = new client.Histogram({
  name: 'http_request_duration_seconds', help: 'HTTP request latency by route template', labelNames: ['route'],
});

// ── C2 the schemas ───────────────────────────────────────────────────────────────────────────────────────────────
const ItemIn = z.object({
  name: z.string().min(1).max(64),
  tags: z.array(z.string()).max(5).default([]),
});
const ListQuery = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
  offset: z.coerce.number().int().min(0).default(0),
});
const ItemParams = z.object({ id: z.coerce.number().int().min(1) });

// ── C3 errors ────────────────────────────────────────────────────────────────────────────────────────────────────
class ApiError extends Error {
  constructor(status, code, message, fields) {
    super(message);
    Object.assign(this, { status, code, fields });
  }
}

const fieldsOf = (zodError) => zodError.issues.map((i) => ({ field: String(i.path[0] ?? 'body'), message: i.message }));

/** validate({body, query, params}): parse each part with its schema into req.valid, or a 422 ApiError. */
function validate(schemas) {
  return (req, _res, next) => {
    req.valid = {};
    for (const [part, schema] of Object.entries(schemas)) {
      const parsed = schema.safeParse(req[part] ?? {});
      if (!parsed.success) return next(new ApiError(422, 'validation_failed', 'the request is invalid', fieldsOf(parsed.error)));
      req.valid[part] = parsed.data;
    }
    return next();
  };
}

// Express 4 does not catch a rejected promise from a handler; this hands it to the error middleware.
const route = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

function envelope(res, status, code, message, fields) {
  const error = { code, message, request_id: res.locals.requestId };
  if (fields) error.fields = fields;
  res.status(status).json({ error });
}

// ── the app ──────────────────────────────────────────────────────────────────────────────────────────────────────
/**
 * The wired app WITHOUT listening. settings defaults to loadSettings() (the env, validated now), store to the
 * in-memory one; log receives each access-log / error line (console.log by default); extraRoutes adds routes before
 * the error middleware (the tests' /boom).
 */
function createApp({ settings = loadSettings(), store = new InMemoryItemStore(), log = console.log, extraRoutes } = {}) {
  const app = express();
  let ready = false;
  app.locals.lifecycle = {
    async start() { await store.open(); ready = true; },
    async stop() { ready = false; await store.close(); },
  };

  // C4 + C5: request id, access log and metrics, recorded when the response finishes.
  app.use((req, res, next) => {
    const rid = req.get('x-request-id') || crypto.randomUUID().replaceAll('-', '');
    res.locals.requestId = rid;
    res.set('X-Request-ID', rid);
    const started = process.hrtime.bigint();
    res.on('finish', () => {
      const seconds = Number(process.hrtime.bigint() - started) / 1e9;
      const template = req.route ? req.baseUrl + req.route.path : 'unmatched';
      requests.inc({ route: template, status: String(res.statusCode) });
      latency.observe({ route: template }, seconds);
      log(JSON.stringify({ method: req.method, path: req.path, status: res.statusCode, request_id: rid,
        duration_ms: Math.round(seconds * 1e6) / 1e3 }));
    });
    next();
  });
  app.use(express.json());

  app.get('/health', (_req, res) => res.json({ status: 'ok' }));
  app.get('/ready', (_req, _res, next) => (ready ? _res.json({ status: 'ready' })
    : next(new ApiError(503, 'not_ready', 'the service is starting'))));
  app.get('/metrics', route(async (_req, res) => {
    res.set('Content-Type', client.register.contentType);
    res.end(await client.register.metrics());
  }));
  app.get('/hello', (_req, res) => {
    helloHits.inc();
    res.json({ service: SERVICE_NAME, message: settings.greeting });
  });

  app.get('/items', validate({ query: ListQuery }), route(async (req, res) => {
    const { limit, offset } = req.valid.query;
    res.json({ items: await store.list(limit, offset), limit, offset });
  }));
  app.get('/items/:id', validate({ params: ItemParams }), route(async (req, res) => {
    const found = await store.get(req.valid.params.id);
    if (!found) throw new ApiError(404, 'not_found', `item ${req.valid.params.id} not found`);
    res.json(found);
  }));
  app.post('/items', validate({ body: ItemIn }), route(async (req, res) => {
    res.status(201).json(await store.create(req.valid.body.name, req.valid.body.tags));
  }));
  if (extraRoutes) extraRoutes(app);

  // C3: anything unmatched, then the one error middleware (Express knows it by its four arguments).
  app.use((req, _res, next) => next(new ApiError(404, 'not_found', `no route for ${req.method} ${req.path}`)));
  // eslint-disable-next-line no-unused-vars
  app.use((err, _req, res, _next) => {
    if (err instanceof ApiError) return envelope(res, err.status, err.code, err.message, err.fields);
    if (err.type === 'entity.parse.failed') {        // express.json() on a malformed body
      return envelope(res, 422, 'validation_failed', 'the request is invalid', [{ field: 'body', message: 'malformed JSON' }]);
    }
    log(JSON.stringify({ event: 'unhandled_error', request_id: res.locals.requestId, error: String(err.stack || err) }));
    return envelope(res, 500, 'internal', 'internal error');   // the detail goes to the log, never to the client
  });
  return app;
}

/**
 * C8: listen, open the store, flip /ready. shutdown() stops accepting, waits for in-flight requests to finish
 * (server.close), then closes the store.
 */
async function serve(app, { port = 8080, host = '0.0.0.0' } = {}) {
  const server = await new Promise((resolve) => { const s = app.listen(port, host, () => resolve(s)); });
  await app.locals.lifecycle.start();
  return {
    server,
    async shutdown() {
      await new Promise((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));
      await app.locals.lifecycle.stop();
    },
  };
}

module.exports = { createApp, serve, ApiError, SERVICE_NAME };

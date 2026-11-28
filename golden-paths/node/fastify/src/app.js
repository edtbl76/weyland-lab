// Golden path — Node / Fastify (B153; deep contract v2 since B262). Runnable, ephemeral, extendable.
//
// The minimal contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Deep contract v2 (docs/concepts/golden-path-capabilities.md), each row in Fastify's own idiom:
//   C1 routing      GET /items?limit&offset, GET /items/:id, POST /items
//   C2 validation   JSON Schema on each route (built in, Ajv); a bad request is 422 with per-field errors
//   C3 errors       one envelope {"error": {code, message, request_id}} from setErrorHandler + setNotFoundHandler
//   C4 middleware   requestIdHeader/genReqId (native X-Request-ID) + an onResponse hook: one JSON access-log line
//   C5 metrics      http_requests_total{route,status} + http_request_duration_seconds{route}, per route template
//   C6 config       loadSettings(): GOLDEN_GREETING validated when the app is built (empty = refuse to start)
//   C7 DI           the store is a decorator (app.store), in-memory by default
//   C8 lifecycle    lifecycle.start() opens the store after listen and flips /ready; an onClose hook closes it, and
//                   app.close() drains in-flight requests first. (onReady runs before any request is accepted, so a
//                   store opened there would leave /ready no 503 window.)
//   C9 tests        app.inject(), one test per row (test/app.test.js), node:test
//   C10 OpenAPI     skipped: no native document without a plugin
//   C11 tracing     setupTracing() (src/shared/tracing.js), started by server.js before Fastify loads
//
// Note: Ajv still coerces scalars (needed for the query string), so a tag sent as 1 binds as "1": still a string, so
// the typed contract holds. Scaffold FROM it: scripts/new-service.sh node/fastify <your-service>.
'use strict';

const crypto = require('node:crypto');
const Fastify = require('fastify');
const client = require('prom-client');
const { loadSettings } = require('./shared/settings');
const { InMemoryItemStore } = require('./shared/items-store');

// The one place a scaffolded service is renamed (scripts/new-service.sh rewrites this token).
const SERVICE_NAME = 'golden-node-fastify';

const helloHits = new client.Counter({ name: 'golden_hello_requests_total', help: 'Calls to the demo /hello endpoint' });
const requests = new client.Counter({
  name: 'http_requests_total', help: 'HTTP requests by route template and status', labelNames: ['route', 'status'],
});
const latency = new client.Histogram({
  name: 'http_request_duration_seconds', help: 'HTTP request latency by route template', labelNames: ['route'],
});

// ── C2 the schemas ───────────────────────────────────────────────────────────────────────────────────────────────
const ItemIn = {
  type: 'object', required: ['name'], additionalProperties: false,
  properties: {
    name: { type: 'string', minLength: 1, maxLength: 64 },
    tags: { type: 'array', items: { type: 'string' }, maxItems: 5, default: [] },
  },
};
const Item = {
  type: 'object',
  properties: { id: { type: 'integer' }, name: { type: 'string' }, tags: { type: 'array', items: { type: 'string' } } },
};
const ListQuery = {
  type: 'object',
  properties: {
    limit: { type: 'integer', minimum: 1, maximum: 100, default: 20 },
    offset: { type: 'integer', minimum: 0, default: 0 },
  },
};
const ItemParams = { type: 'object', properties: { id: { type: 'integer', minimum: 1 } } };

// ── C3 errors ────────────────────────────────────────────────────────────────────────────────────────────────────
class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    Object.assign(this, { status, code });
  }
}

/** Ajv's errors as {field, message}: the property a rule names (missing/extra) or the top-level property it failed. */
const fieldsOf = (validation) => validation.map((v) => ({
  field: v.params?.missingProperty || v.params?.additionalProperty || v.instancePath.split('/')[1] || 'body',
  message: v.message,
}));

function envelope(request, reply, status, code, message, fields) {
  const error = { code, message, request_id: request.id };
  if (fields) error.fields = fields;
  return reply.code(status).send({ error });
}

// ── the app ──────────────────────────────────────────────────────────────────────────────────────────────────────
/**
 * The wired Fastify instance WITHOUT listening. settings defaults to loadSettings() (the env, validated now), store
 * to the in-memory one; log receives each access-log / error line (console.log by default); extraRoutes adds routes
 * (the tests' /boom).
 */
function build({ settings = loadSettings(), store = new InMemoryItemStore(), log = console.log, extraRoutes } = {}) {
  const app = Fastify({
    logger: false,                                        // the JSON access log below is the contract's, not pino's
    requestIdHeader: 'x-request-id',
    genReqId: () => crypto.randomUUID().replaceAll('-', ''),
    // Fastify's default is coerceTypes: 'array', which wraps a scalar into a one-element array (tags: "x" would bind
    // as ["x"]). Scalar coercion stays (a query string is all strings), array wrapping goes.
    ajv: { customOptions: { coerceTypes: true } },
  });
  let ready = false;
  app.decorate('store', store);
  app.decorate('lifecycle', {
    async start() { await store.open(); ready = true; },
  });
  app.addHook('onClose', async () => { ready = false; await store.close(); });

  // C4 + C5
  app.addHook('onSend', async (request, reply) => { reply.header('X-Request-ID', request.id); });
  app.addHook('onResponse', async (request, reply) => {
    const template = request.routeOptions.url || 'unmatched';
    requests.inc({ route: template, status: String(reply.statusCode) });
    latency.observe({ route: template }, reply.elapsedTime / 1e3);
    log(JSON.stringify({ method: request.method, path: request.url.split('?')[0], status: reply.statusCode,
      request_id: request.id, duration_ms: Math.round(reply.elapsedTime * 1e3) / 1e3 }));
  });

  // C3
  app.setNotFoundHandler((request, reply) => envelope(request, reply, 404, 'not_found',
    `no route for ${request.method} ${request.url.split('?')[0]}`));
  app.setErrorHandler((err, request, reply) => {
    if (err instanceof ApiError) return envelope(request, reply, err.status, err.code, err.message);
    if (err.validation) return envelope(request, reply, 422, 'validation_failed', 'the request is invalid', fieldsOf(err.validation));
    if (err.code === 'FST_ERR_CTP_INVALID_JSON_BODY' || err.code === 'FST_ERR_CTP_EMPTY_JSON_BODY') {
      return envelope(request, reply, 422, 'validation_failed', 'the request is invalid', [{ field: 'body', message: 'malformed JSON' }]);
    }
    log(JSON.stringify({ event: 'unhandled_error', request_id: request.id, error: String(err.stack || err) }));
    return envelope(request, reply, 500, 'internal', 'internal error');   // the detail goes to the log only
  });

  app.get('/health', async () => ({ status: 'ok' }));
  app.get('/ready', async () => {
    if (!ready) throw new ApiError(503, 'not_ready', 'the service is starting');
    return { status: 'ready' };
  });
  app.get('/metrics', async (_req, reply) => {
    reply.header('Content-Type', client.register.contentType);
    return client.register.metrics();
  });
  app.get('/hello', async () => {
    helloHits.inc();
    return { service: SERVICE_NAME, message: settings.greeting };
  });

  app.get('/items', { schema: { querystring: ListQuery } }, async (request) => {
    const { limit, offset } = request.query;
    return { items: await app.store.list(limit, offset), limit, offset };
  });
  app.get('/items/:id', { schema: { params: ItemParams, response: { 200: Item } } }, async (request) => {
    const found = await app.store.get(request.params.id);
    if (!found) throw new ApiError(404, 'not_found', `item ${request.params.id} not found`);
    return found;
  });
  app.post('/items', { schema: { body: ItemIn, response: { 201: Item } } }, async (request, reply) => {
    reply.code(201);
    return app.store.create(request.body.name, request.body.tags);
  });
  if (extraRoutes) extraRoutes(app);
  return app;
}

/** C8: listen, then open the store and flip /ready. shutdown() is app.close(): drain, then the onClose hook. */
async function serve(app, { port = 8080, host = '0.0.0.0' } = {}) {
  await app.listen({ port, host });
  await app.lifecycle.start();
  return { port: app.server.address().port, shutdown: () => app.close() };
}

module.exports = { build, serve, ApiError, SERVICE_NAME };

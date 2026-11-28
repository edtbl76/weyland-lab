# Golden path — Node / Fastify

Blessed paved-road Fastify service. **Runnable · ephemeral · extendable.** Meets the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md): `/health` `/ready` `/metrics` `/hello`) and deep
contract v2 ([docs/concepts/golden-path-capabilities.md](../../../docs/concepts/golden-path-capabilities.md)), B262.

```
npm install && node --test                 # 32 tests (node:test + app.inject(), no test-runner dependency), 100%
node --test ./selfcheck/*.selfcheck.js     # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh javascript  # the CI lane runs this golden path
```

## Deep contract v2, in Fastify's idiom

| Row | Here |
|---|---|
| C1 routing | `GET /items?limit&offset`, `GET /items/:id`, `POST /items` |
| C2 validation | JSON Schema on each route (built in, Ajv); a bad body, query, id or malformed JSON is **422** with per-field errors |
| C3 errors | one envelope from `setErrorHandler` + `setNotFoundHandler`; 500 hides the detail (it goes to the log) |
| C4 middleware | `requestIdHeader` / `genReqId` (native `X-Request-ID`) + an `onResponse` hook: one JSON access-log line |
| C5 metrics | `http_requests_total{route,status}` + `http_request_duration_seconds{route}`, by route template |
| C6 config | `GOLDEN_GREETING`, validated when the app is built: empty refuses to start |
| C7 DI | a decorator: `app.store`, in-memory by default |
| C8 lifecycle | the store opens after `listen` (so `/ready` has its 503 window: `onReady` runs before any request is accepted); `app.close()` drains, then the `onClose` hook closes the store |
| C9 tests | `app.inject()`, one test per row (`test/app.test.js`) |
| C10 OpenAPI | skipped: no native document without a plugin |
| C11 tracing | an OTel server span per request when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; `test/tracing.test.js` receives the real server's span over OTLP/HTTP |

**Ajv note:** Fastify's default `coerceTypes: 'array'` wraps a scalar into an array (`tags: "x"` would bind as `["x"]`),
so this path sets `coerceTypes: true`: scalars still coerce (the query string is all strings), arrays are not invented.

The shared parts are synced copies of [golden-paths-shared/node/](../../../golden-paths-shared/node/README.md) (edit
the source there; ADR-0020). The integration tier, the image and the smoke work exactly as in the
[Express path](../express/README.md): `integration-node` runs `integration/*.integration.js` against real backends, and
`.smoke` runs the shared v2 sequence against `node src/server.js`.

Scaffold: `scripts/new-service.sh node/fastify <your-service>`.

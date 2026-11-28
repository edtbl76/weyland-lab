# Golden path — Node / Express

Blessed paved-road Express service. **Runnable · ephemeral · extendable.** Meets the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md): `/health` `/ready` `/metrics` `/hello`) and deep
contract v2 ([docs/concepts/golden-path-capabilities.md](../../../docs/concepts/golden-path-capabilities.md)), B262.

```
npm install && npm test                    # 32 tests (jest + supertest), 100% statement coverage
npm run test:selfcheck                     # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh javascript  # the CI lane runs this golden path
```

## Deep contract v2, in Express's idiom

| Row | Here |
|---|---|
| C1 routing | `GET /items?limit&offset`, `GET /items/:id`, `POST /items` |
| C2 validation | zod schemas in a `validate()` middleware; a bad body, query, id or malformed JSON is **422** with per-field errors |
| C3 errors | one envelope `{"error": {code, message, request_id}}` from the 4-argument error middleware; 404 for an unknown id or route, 500 hides the detail (it goes to the log) |
| C4 middleware | `X-Request-ID` echoed or generated; one JSON access-log line per request (`app.use`) |
| C5 metrics | `http_requests_total{route,status}` + `http_request_duration_seconds{route}`, by route template |
| C6 config | `GOLDEN_GREETING` (default `hello, weyland`), validated when the app is built: empty refuses to start |
| C7 DI | none native: `createApp({store})` is the factory; in-memory by default, the real backends by env |
| C8 lifecycle | `/ready` is 503 until the store is open; SIGTERM drains in-flight requests (`server.close`), then closes the store |
| C9 tests | supertest against `createApp()`, one test per row (`test/app.test.js`) |
| C10 OpenAPI | skipped: Express produces no native document |
| C11 tracing | an OTel server span per request when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, a no-op otherwise; `test/tracing.test.js` runs the real `src/server.js` and receives its span over OTLP/HTTP |

The framework-neutral parts (the store, settings, the real backends, tracing, the v2 smoke and the backend tests) are
synced copies of [golden-paths-shared/node/](../../../golden-paths-shared/node/README.md), each headed `// GENERATED`:
edit the source there, never a copy (`scripts/sync-golden-shared.sh`; ADR-0020).

## Integration tier (real backends)

`integration/` runs only in the `integration-node` CI step (`.woodpecker/golden-integration.yml`), against real
Postgres, Valkey, Redpanda and MinIO sidecars: the shared adapters (`items-backends.integration.js`) and this path's HTTP
API on Postgres (`api-postgres.integration.js`). The files are `*.integration.js`, so the unit lane never runs them. The
clients (pg, ioredis, kafkajs, @aws-sdk/client-s3) are devDependencies: never in the image. A service that sets
`GOLDEN_DATABASE_URL` moves the clients it uses into `dependencies`.

## Image and smoke

The image runs `node src/server.js` on `0.0.0.0:8080` (`PORT` overrides). `.smoke` runs the shared v2 sequence against
it, which is what the ephemeral Job (`scripts/run-golden-path-jobs.sh`) asserts:

```
docker build -q -t golden-node-express:local . && docker run --rm golden-node-express:local sh -c "$(cat .smoke)"
```

Scaffold: `scripts/new-service.sh node/express <your-service>`; the onboarding declaration works as in the
[FastAPI reference](../../python/fastapi/README.md).

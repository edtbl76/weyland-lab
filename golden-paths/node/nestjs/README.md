# Golden path — Node / NestJS

Blessed paved-road NestJS service in TypeScript. **Runnable · ephemeral · extendable.** Meets the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md): `/health` `/ready` `/metrics` `/hello`) and deep
contract v2 ([docs/concepts/golden-path-capabilities.md](../../../docs/concepts/golden-path-capabilities.md)), B262.

```
npm install && npm test                    # 35 tests (@nestjs/testing + supertest, jest/ts-jest)
npm run test:selfcheck                     # the deliberate failure (proves the lane propagates)
npm run build && node dist/main.js         # serves on 0.0.0.0:8080 (PORT overrides)
bash scripts/run-lang-tests.sh typescript  # the CI lane runs this golden path
```

## Deep contract v2, in Nest's idiom

| Row | Here |
|---|---|
| C1 routing | `ItemsController`: `GET /items?limit&offset`, `GET /items/:id`, `POST /items` |
| C2 validation | class-validator DTOs (`items.dto.ts`) + the global `ValidationPipe` (`transform: true`); a bad body, query, id or malformed JSON is **422** with per-field errors |
| C3 errors | one envelope from a catch-all exception filter (`errors.ts`); 500 hides the detail (it goes to the log) |
| C4 middleware | `RequestContextMiddleware`: `X-Request-ID` + one JSON access-log line, applied globally ahead of the body parser, so even an unparseable request is logged |
| C5 metrics | `http_requests_total{route,status}` + `http_request_duration_seconds{route}`, by route template |
| C6 config | the `SETTINGS` provider validates `GOLDEN_GREETING` as the app is built: empty refuses to start |
| C7 DI | modules and providers: the `ITEM_STORE` token, in-memory by default (`AppModule.forRoot`) |
| C8 lifecycle | `Lifecycle.start()` after `listen` flips `/ready` (`OnModuleInit` would leave no 503 window); `app.close()` drains, then `OnApplicationShutdown` closes the store |
| C9 tests | `createApp()` + supertest, one test per row (`test/app.test.ts`) |
| C10 OpenAPI | `@nestjs/swagger`, native: `/openapi.json` (no UI) |
| C11 tracing | `main.ts` starts tracing before Nest loads; `test/tracing.test.ts` builds the app and receives the real server's span over OTLP/HTTP |

**Nest notes:** `NestFactory.create` runs with `abortOnError: false` (a startup error is thrown to the caller instead of
`process.exit(1)`) and `bodyParser: false` (so the request context runs first, then Nest's JSON parser, then a
translation of a malformed body into the 422: Nest would map it to a bare 400). `enableShutdownHooks()` is not used:
Nest's handler re-raises SIGTERM after closing and the process exits before tracing flushes; `main.ts` owns the signal.

The shared parts are synced copies of [golden-paths-shared/node/](../../../golden-paths-shared/node/README.md),
compiled in with `allowJs` (edit the source there; ADR-0020). The integration tier, the image and the smoke work as in
the [Express path](../express/README.md); here `integration-node` builds `dist/` first and the integration test drives
the compiled app, and `.smoke` runs the shared v2 sequence against `node dist/main.js`.

Scaffold: `scripts/new-service.sh node/nestjs <your-service>`; its OpenAPI is captured from `/openapi.json` as in the
[FastAPI reference](../../python/fastapi/README.md).

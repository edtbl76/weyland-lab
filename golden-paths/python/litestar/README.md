# Golden path — Python / litestar

Blessed paved-road Litestar service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)) and to deep contract v2
([docs/concepts/golden-path-capabilities.md](../../../docs/concepts/golden-path-capabilities.md), B261).

```
pip install -r requirements.txt
uvicorn --factory main:serve --host 127.0.0.1 --port 8080          # run locally
bash scripts/run-lang-tests.sh python              # the CI lane runs this golden path's tests
```

## Deep contract v2, in Litestar's idiom

| Row | Here |
|---|---|
| C1 routing | `/items`, `/items/{item_id:int}` (`FromPath[int]`) |
| C2 validation | msgspec `Struct` body (`JSONBody[ItemIn]`) + `Parameter(ge, le)`; invalid = 422 with `fields` |
| C3 errors | exception handlers for `ApiError`, `ValidationException`, `HTTPException` and `Exception` |
| C4/C5 middleware | an ASGI middleware: `X-Request-ID`, JSON access log, per-route metrics (`path_template`) |
| C6 config | `Settings.from_env()`: `GOLDEN_GREETING`, validated at startup |
| C7 DI | `Provide` + `NamedDependency[Any]` (msgspec cannot validate a Protocol; the contract is `ItemStore`) |
| C8 lifecycle | `on_startup` opens the store and flips `/ready` (503 before); `on_shutdown` closes it |
| C10 OpenAPI | native, `/schema/openapi.json` |
| C11 tracing | Litestar's `OpenTelemetryPlugin` (from `litestar.plugins.opentelemetry`) when tracing is on |
| C9 tests | the framework's test client, `test_main.py` (100% of `main.py` and the shared store) |

**Shared code** (`items_store.py`, `items_backends.py`, `v2_smoke.py`, `integration/conftest.py`,
`integration/test_items_backends.py`, `requirements-integration.txt`) is a synced copy of
[golden-paths-shared/python/](../../../golden-paths-shared/python/README.md): edit the source, never the copy
(`scripts/sync-golden-shared.sh`; ADR-0020). **Real backends:** set `GOLDEN_DATABASE_URL` (plus the optional
`GOLDEN_VALKEY_URL` / `GOLDEN_KAFKA_BOOTSTRAP`) and the service uses them; `integration/` tests them in CI
(`.woodpecker/golden-integration.yml`).

**Ephemeral Job + scaffolding + the onboarding declaration** work exactly as the FastAPI reference — see
[../fastapi/README.md](../fastapi/README.md). `smoke.py` starts the real server and runs the shared v2 sequence.
Scaffold: `scripts/new-service.sh python/litestar <your-service>`.

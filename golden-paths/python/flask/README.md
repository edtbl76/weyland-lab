# Golden path — Python / flask

Blessed paved-road Flask service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)) and to deep contract v2
([docs/concepts/golden-path-capabilities.md](../../../docs/concepts/golden-path-capabilities.md), B261).

```
pip install -r requirements.txt
gunicorn -b 127.0.0.1:8080 'main:serve()'          # run locally
bash scripts/run-lang-tests.sh python              # the CI lane runs this golden path's tests
```

## Deep contract v2, in Flask's idiom

| Row | Here |
|---|---|
| C1 routing | `/items`, `/items/<int:item_id>` |
| C2 validation | marshmallow schemas (`ItemIn`, `Paging`); Flask has none native; invalid = 422 with `fields` |
| C3 errors | `errorhandler`s for `ApiError`, `ValidationError`, `HTTPException` and anything unhandled |
| C4/C5 middleware | `before_request`/`after_request`: `X-Request-ID`, JSON access log, per-route metrics (`url_rule`) |
| C6 config | `Settings.from_env()`: `GOLDEN_GREETING`, validated at startup |
| C7 DI | **skip** (Flask has none native): the shared store on `app.extensions["golden"]` |
| C8 lifecycle | the app factory opens the store and flips `/ready` (503 before); `app_shutdown()` at exit |
| C10 OpenAPI | **skip** for Flask (catalog) |
| C11 tracing | `FlaskInstrumentor` when `OTEL_EXPORTER_OTLP_ENDPOINT` is set |
| C9 tests | the framework's test client, `test_main.py` (100% of `main.py` and the shared store) |

**Shared code** (`items_store.py`, `items_backends.py`, `v2_smoke.py`, `integration/conftest.py`,
`integration/test_items_backends.py`, `requirements-integration.txt`) is a synced copy of
[golden-paths-shared/python/](../../../golden-paths-shared/python/README.md): edit the source, never the copy
(`scripts/sync-golden-shared.sh`; ADR-0020). **Real backends:** set `GOLDEN_DATABASE_URL` (plus the optional
`GOLDEN_VALKEY_URL` / `GOLDEN_KAFKA_BOOTSTRAP`) and the service uses them; `integration/` tests them in CI
(`.woodpecker/golden-integration.yml`).

**Ephemeral Job + scaffolding + the onboarding declaration** work exactly as the FastAPI reference — see
[../fastapi/README.md](../fastapi/README.md). `smoke.py` starts the real server and runs the shared v2 sequence.
Scaffold: `scripts/new-service.sh python/flask <your-service>`.

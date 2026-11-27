# Golden path — Python / FastAPI

The blessed paved-road FastAPI service. **Runnable · ephemeral · extendable.** Conforms to the
golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)):
`GET /health` · `/ready` · `/metrics` · `/hello`.

## Run it (locally)

```
pip install -r requirements.txt
uvicorn main:app --port 8080          # then: curl localhost:8080/hello -> {"service":"golden-python-fastapi","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
bash scripts/run-lang-tests.sh python              # discovers + runs this golden path's tests
bash scripts/run-lang-tests.sh python --self-check # proves the lane propagates the selfcheck failure
```

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

`k8s/golden-paths/` carries the run-to-completion Job: buildkit builds `registry.weyland.lab/golden-python-fastapi`,
the Job starts it, asserts `/ready` + `/hello`'s known payload, exits 0, and is deleted. Never a Deployment.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh python/fastapi <your-service>
```

Rewrites `SERVICE_NAME`, fills the onboarding declaration below, and gives you a runnable, gate-passing
starting point. The declaration is what makes the scaffolded service pass the onboarding gates (B154/B155)
**by construction** — fill each `<...>` and the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh (it's FastAPI → OpenAPI captured) ---
- {id: <your-service>, owner: <your-service>, kind: openapi, status: published, version: "1.0",
   base: "http://<your-service>.weyland.svc:8080",
   spec: docs/api/specs/<your-service>.openapi.json,
   spec_source: "http://<your-service>.weyland.svc:8080/openapi.json", consumers: []}
```

```
# --- weyland.likec4 (add to the right zone) ---
yourServiceCamelId = component "Your Service" "<one line>"
```

After scaffolding: capture the OpenAPI snapshot (`curl .../openapi.json > docs/api/specs/<svc>.openapi.json`),
run `scripts/gen-api-contract-lock.sh`, and the onboarding + API-lifecycle guards pass.

## Contract compliance

| Facet | This golden path |
|---|---|
| HTTP surface | `/health` `/ready` `/metrics` `/hello`, plus the deep contract v2 `/items` API (main.py) |
| Self-test | `test_main.py` (TestClient, one test per v2 row, 100% coverage) + `selfcheck/` (deliberate fail) |
| Build | multi-stage non-root `Dockerfile` → `registry.weyland.lab/golden-python-fastapi` |
| Observability | JSON access log with `X-Request-ID`, per-route `/metrics`, OTel spans when `OTEL_EXPORTER_OTLP_ENDPOINT` is set |
| API lifecycle | OpenAPI at `/openapi.json` (FastAPI-native) → captured by B155 |

## Deep contract v2 (B163 / B260) — the reference implementation

Every row of [the deep contract](../../../docs/concepts/golden-path-capabilities.md), in FastAPI's own idiom:

| Row | Here |
|---|---|
| C1 routing | `GET /items?limit&offset`, `GET /items/{item_id}`, `POST /items` |
| C2 validation | Pydantic `ItemIn` (name 1-64, ≤ 5 tags) and `Query(ge=, le=)`; invalid = 422 with `fields` |
| C3 errors | exception handlers → `{"error": {"code", "message", "request_id"}}` for 404/405/422/500/503 |
| C4 middleware | `@app.middleware("http")`: `X-Request-ID` echoed or generated; one JSON access-log line |
| C5 metrics | `http_requests_total{route,status}`, `http_request_duration_seconds` (route = the template) |
| C6 config | `Settings.from_env()`: `GOLDEN_GREETING`, validated at startup (empty refuses to start) |
| C7 DI | the shared `ItemStore` via `Depends(get_store)`; in-memory by default, the real backends by env |
| C8 lifecycle | `lifespan` opens the store and flips `/ready` (503 before); uvicorn drains on SIGTERM |
| C9 tests | `TestClient`, `test_main.py` |
| C10 OpenAPI | `/openapi.json` |
| C11 tracing | `setup_tracing()`: OTLP export when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, a no-op otherwise |

**Shared code** (`items_store.py`, `items_backends.py`, `v2_smoke.py`, `integration/conftest.py`,
`integration/test_items_backends.py`, `requirements-integration.txt`) is a synced copy of
[golden-paths-shared/python/](../../../golden-paths-shared/python/README.md): edit the source, never the copy
(`scripts/sync-golden-shared.sh`; ADR-0020). **Real backends:** set `GOLDEN_DATABASE_URL` (Postgres), and optionally
`GOLDEN_VALKEY_URL` (read-through cache) and `GOLDEN_KAFKA_BOOTSTRAP` (`item.created` events): `main.py` builds the
store from them. `integration/` tests them against real backends in CI (`.woodpecker/golden-integration.yml`); its
conftest refuses to run without them, and the unit lane ignores it.

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
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (main.py) |
| Self-test | `tests/test_main.py` (TestClient over all four) + `selfcheck/` (deliberate fail) |
| Build | multi-stage non-root `Dockerfile` → `registry.weyland.lab/golden-python-fastapi` |
| Observability | structured JSON logging + `/metrics` (prometheus-client counter) |
| API lifecycle | OpenAPI at `/openapi.json` (FastAPI-native) → captured by B155 |

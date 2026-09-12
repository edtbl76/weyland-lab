# Golden path — R / plumber

The blessed paved-road **R** service (an HTTP service on [`plumber`](https://www.rplumber.io/) —
**not** Shiny). **Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `GET /health` · `/ready` ·
`/metrics` · `/hello`. Binds `0.0.0.0:8080`.

## Run it (locally)

```
Rscript entrypoint.R          # then: curl localhost:8080/hello -> {"service":"golden-r-plumber","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
Rscript -e 'testthat::test_dir("tests")'                        # 5 contract tests pass; selfcheck is unarmed (exit 0)
GOLDEN_SELFCHECK=1 Rscript -e 'testthat::test_dir("tests")'     # the deliberate failure — arms + runs it, exits non-zero (proves the lane propagates)
Rscript -e 'lintr::lint_dir(".")'                               # scan lane (proposed) — lintr; see "Scan" below
```

The contract tests exercise the **pure payload builders** in `payloads.R` headless — the C/C++
golden-path pattern. plumber binds `httpuv` to a real socket, so rather than stand the server up
in-process the suite asserts on the exact payload shapes and the exact `/hello` JSON bytes each
endpoint emits; the running image is then proven by the curl smoke (`smoke.sh` / `.smoke`).

**selfcheck gating:** the deliberate failure lives in `tests/test-selfcheck.R` behind
`GOLDEN_SELFCHECK=1`. Unset (a normal run), the file registers **zero** tests, so the guard cannot
fail open on a no-match. Set, it registers a test that fails with a **named reason** (not a bare
non-zero exit), so a real failure is distinguishable from a missing test — per the estate's
"an absent result is never success" rule.

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

Works as the Python FastAPI reference — see [../../python/fastapi/README.md](../../python/fastapi/README.md)
and `scripts/run-golden-path-jobs.sh` (reads `.smoke`). buildkit builds
`registry.weyland.lab/golden-r-plumber`, the run-to-completion Job starts it, asserts `/ready` +
`/hello`'s known payload via `smoke.sh`, exits 0, and is deleted. Never a Deployment.

## Scan

No R scanner is wired into `run-lang-scan.sh` / `quality-tools.yaml` yet (R is an optional-wave
language). Proposed standard: **`lintr`** (`Rscript -e 'lintr::lint_dir(".")'`) — the estate's
lang-scan idiom (one on-PATH linter per lane, fail-closed on the printed findings, not `$?`). It is
not installed in this golden path's image; a lane registration would add it to the toolchain image +
`quality-tools.yaml`.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh r/plumber <your-service>
```

Rewrites `SERVICE_NAME`, fills the onboarding declaration below, and gives you a runnable,
gate-passing starting point. The declaration is what makes the scaffolded service pass the
onboarding gates (B154/B155) **by construction** — fill each `<...>` and the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
# plumber CAN emit an OpenAPI/Swagger doc (it mounts /__docs__ + /openapi.json when the router
# runs), but the golden path serves only the four contract endpoints. For a real service either
# capture /openapi.json as spec_source, or author the spec by hand and point `spec` at it.
- {id: <your-service>, owner: <your-service>, kind: openapi, status: published, version: "1.0",
   base: "http://<your-service>.weyland.svc:8080",
   spec: docs/api/specs/<your-service>.openapi.json, consumers: []}
```

```
# --- weyland.likec4 (add to the right zone) ---
yourServiceCamelId = component "Your Service" "<one line>"
```

After scaffolding: author `docs/api/specs/<svc>.openapi.json`, run `scripts/gen-api-contract-lock.sh`,
and the onboarding + API-lifecycle guards pass.

## Contract compliance

| Facet | This golden path |
|---|---|
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (`plumber.R`, served by `entrypoint.R`; bodies delegate to the pure builders in `payloads.R`) |
| Self-test | `tests/test-contract.R` (5 tests over the pure payload builders + exact `/hello` JSON bytes) + `tests/test-selfcheck.R` (deliberate fail, gated by `GOLDEN_SELFCHECK=1`) |
| Build | multi-stage non-root `Dockerfile` (`rocker/r-ver:4` install → `rocker/r-ver:4` run, `USER 10001`) → `registry.weyland.lab/golden-r-plumber` |
| Observability | structured JSON logging on startup + `/metrics` (Prometheus text exposition 0.0.4, hello counter) |
| Toolchain | `rocker/r-ver:4`; root marker `plumber.R`; test glob `test-*.R`; test cmd `Rscript -e 'testthat::test_dir("tests")'`; selfcheck `GOLDEN_SELFCHECK=1 Rscript -e 'testthat::test_dir("tests")'` |

# Golden path — Julia / Oxygen.jl

The blessed paved-road Oxygen.jl service. **Runnable · ephemeral · extendable.** Conforms to the
golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)):
`GET /health` · `/ready` · `/metrics` · `/hello` on port 8080.

## Run it (locally)

```
julia --project=. -e 'using Pkg; Pkg.instantiate()'   # first time: resolve the pinned Manifest
julia --project=. main.jl                             # then: curl localhost:8080/hello
#   -> {"service":"golden-julia-oxygen","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
julia --project=. -e 'using Pkg; Pkg.test()'                     # 11 contract assertions over the four routes
GOLDEN_SELFCHECK=1 julia --project=. -e 'using Pkg; Pkg.test()'  # the deliberate failure (proves the lane propagates; exits non-zero)
```

The self-test starts the real Oxygen server on an ephemeral port and drives `/health` `/ready`
`/hello` `/metrics` over HTTP (`test/runtests.jl`). The **selfcheck** set is excluded from a normal run
and only runs under `GOLDEN_SELFCHECK=1` (or `Pkg.test(test_args=["selfcheck"])`); it is fail-closed —
a green selfcheck run means the failure did not surface and the lane is broken.

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

`scripts/run-golden-path-jobs.sh` builds `registry.weyland.lab/golden-julia-oxygen` via buildkit, applies
a run-to-completion Job that starts the image, asserts `/ready` + `/hello`'s known payload (via
`.smoke` → `smoke.sh`), exits 0, and is deleted. Never a Deployment.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh julia/oxygen <your-service>
```

Rewrites `SERVICE_NAME` (`OxygenGolden.SERVICE_NAME` in `src/OxygenGolden.jl`), drops the selfcheck, and
fills the onboarding declaration below. The declaration is what makes the scaffolded service pass the
onboarding gates (B154/B155) **by construction** — fill each `<...>` and the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
# Oxygen can serve an OpenAPI doc + Swagger UI (start(...) here sets docs=false to keep the contract
# surface minimal). To make the scaffold OpenAPI-captured, enable Oxygen's docs (serve(docs=true)),
# snapshot /openapi.json, and use kind: openapi. Otherwise declare kind: none.
- {id: <your-service>, owner: <your-service>, kind: openapi, status: published, version: "1.0",
   base: "http://<your-service>.weyland.svc:8080",
   spec: docs/api/specs/<your-service>.openapi.json,
   spec_source: "http://<your-service>.weyland.svc:8080/openapi.json", consumers: []}
```

```
# --- weyland.likec4 (add to the right zone) ---
yourServiceCamelId = component "Your Service" "<one line>"
```

After scaffolding: capture the OpenAPI snapshot if OpenAPI is enabled
(`curl .../openapi.json > docs/api/specs/<svc>.openapi.json`), run `scripts/gen-api-contract-lock.sh`,
and the onboarding + API-lifecycle guards pass.

## Contract compliance

| Facet | This golden path |
|---|---|
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (`src/OxygenGolden.jl`, Oxygen `@get` routes) |
| Self-test | `test/runtests.jl` (real server + HTTP client over all four) + selfcheck (deliberate fail under `GOLDEN_SELFCHECK=1`) |
| Build | multi-stage non-root `Dockerfile` (julia build → julia runtime, precompiled depot) → `registry.weyland.lab/golden-julia-oxygen` |
| Observability | structured request logging (Oxygen) + `/metrics` (hand-rolled Prometheus counter `golden_hello_requests_total`) |
| Scan | `JuliaFormatter` check (proposed; non-standard — needs `JuliaFormatter` in the lane image): `julia -e 'using JuliaFormatter; exit(format(".", overwrite=false) ? 0 : 1)'` |

## Lane wiring (for the harness engineer — NOT yet wired into shared files)

| Fact | Value |
|---|---|
| Toolchain image | `julia:1.11` (also builds on `julia:1.10`) |
| Root marker | `Project.toml` |
| Test-file glob | `test/runtests.jl` (Pkg.test convention) |
| Test command | `julia --project=. -e 'using Pkg; Pkg.test()'` |
| Selfcheck command | `GOLDEN_SELFCHECK=1 julia --project=. -e 'using Pkg; Pkg.test()'` (must exit non-zero) |
| Scan command | `JuliaFormatter` check (above) — no standard weyland scanner for Julia yet |
| Image | `registry.weyland.lab/golden-julia-oxygen`, port 8080 |

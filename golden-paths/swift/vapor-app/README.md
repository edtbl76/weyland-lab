# Golden path — Swift / Vapor

The blessed paved-road server-side **Swift / Vapor** service (swift.org Linux toolchain — **not**
iOS). **Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `GET /health` · `/ready` ·
`/metrics` · `/hello`.

## Run it (locally, needs a Swift toolchain — or use the image)

```
swift run Run          # then: curl localhost:8080/hello -> {"service":"golden-swift-vapor-app","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
swift test                                          # 4 contract tests (AppTests) pass; SelfCheckTests skips
GOLDEN_SELFCHECK=1 swift test --filter SelfCheckTests   # the deliberate failure (proves the lane propagates)
```

The selfcheck lives in a second test target (`SelfCheckTests`). A bare `swift test` runs it too, so
its `XCTFail` is gated behind `GOLDEN_SELFCHECK=1` and **skipped** otherwise — the bare run is all
green. The lane surfaces the failure by setting that env var and filtering to the target.

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

Works as the Python FastAPI reference — buildkit builds `registry.weyland.lab/golden-swift-vapor-app`,
`scripts/run-golden-path-jobs.sh` (reads `.smoke`) starts a run-to-completion Job that asserts `/ready`
+ `/hello`'s known payload, exits 0, and is deleted. Never a Deployment. See
[../../python/fastapi/README.md](../../python/fastapi/README.md).

## Scaffold a REAL service FROM this

```
scripts/new-service.sh swift/vapor-app <your-service>
```

Rewrites `serviceName` (in `Sources/App/routes.swift`), fills the onboarding declaration below, and
gives you a runnable, gate-passing starting point. The declaration is what makes the scaffolded
service pass the onboarding gates (B154/B155) **by construction** — fill each `<...>` and the guards
go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
- {id: <your-service>, owner: <your-service>, kind: openapi, status: published, version: "1.0",
   base: "http://<your-service>.weyland.svc:8080",
   spec: docs/api/specs/<your-service>.openapi.json,
   spec_source: "", consumers: []}
```

```
# --- weyland.likec4 (add to the right zone) ---
yourServiceCamelId = component "Your Service" "<one line>"
```

Vapor has no built-in OpenAPI emission, so capture/author the spec at
`docs/api/specs/<svc>.openapi.json` and run `scripts/gen-api-contract-lock.sh`; the onboarding +
API-lifecycle guards then pass.

## Contract compliance

| Facet | This golden path |
|---|---|
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (`Sources/App/routes.swift`), bound `0.0.0.0:8080` (`configure.swift`) |
| Self-test | `Tests/AppTests/ContractTests.swift` (XCTVapor over all four) + `Tests/SelfCheckTests/` (env-gated deliberate fail) |
| Build | multi-stage non-root `Dockerfile` (`swift:6.0-jammy` build → `swift:6.0-jammy-slim` runtime) → `registry.weyland.lab/golden-swift-vapor-app` |
| Observability | structured logging (Vapor `Logger`) + `/metrics` (minimal Prometheus counter `golden_hello_requests_total`) |
| Lane facts | runner `swift`; root marker `Package.swift`; tests `Tests/**/*.swift`; scan `swift-format lint` if available (none-standard otherwise) |

## `/hello` payload

```json
{"service":"golden-swift-vapor-app","message":"hello, weyland"}
```

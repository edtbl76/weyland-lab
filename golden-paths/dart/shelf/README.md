# Golden path — server-side Dart / shelf

The blessed paved-road **server-side Dart** service (this is an HTTP service on `shelf` +
`shelf_router` — **not** Flutter). **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `GET /health` ·
`/ready` · `/metrics` · `/hello`. Binds `InternetAddress.anyIPv4:8080`.

## Run it (locally)

```
dart pub get
dart run bin/server.dart      # then: curl localhost:8080/hello -> {"service":"golden-dart-shelf","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
dart test                                  # 4 contract tests pass; selfcheck is skipped (exit 0)
dart test -t selfcheck --run-skipped       # the deliberate failure — runs + exits non-zero (proves the lane propagates)
dart analyze --fatal-infos                 # scan lane — clean
```

**selfcheck gotcha (package:test):** you cannot both exclude a tag from a bare `dart test` via
`dart_test.yaml` AND run it via a bare `dart test -t selfcheck`. A `skip:` tag config makes
`-t selfcheck` report *"All tests skipped"* (exit 0 — a fail-open trap); `exclude_tags` makes it
report *"No tests match"* (exit 79 — non-zero, but the failing test never runs, proving nothing).
The `--run-skipped` flag is what forces the skip-tagged selfcheck to genuinely execute and fail. See
`dart_test.yaml`.

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

Works as the Python FastAPI reference — see [../../python/fastapi/README.md](../../python/fastapi/README.md)
and `scripts/run-golden-path-jobs.sh` (reads `.smoke`). buildkit builds
`registry.weyland.lab/golden-dart-shelf`, the run-to-completion Job starts it, asserts `/ready` +
`/hello`'s known payload via `smoke.sh`, exits 0, and is deleted. Never a Deployment.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh dart/shelf <your-service>
```

Rewrites `serviceName`, fills the onboarding declaration below, and gives you a runnable, gate-passing
starting point. The declaration is what makes the scaffolded service pass the onboarding gates
(B154/B155) **by construction** — fill each `<...>` and the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
# shelf serves no native OpenAPI, so author the spec file by hand (there is no /openapi.json
# spec_source to capture). Point `spec` at the committed doc and omit spec_source.
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
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (`lib/router.dart`, served by `bin/server.dart`) |
| Self-test | `test/contract_test.dart` (drives the handler over all four) + `test/selfcheck_test.dart` (deliberate fail, `@Tags(['selfcheck'])`) |
| Build | multi-stage non-root `Dockerfile` (`dart:stable` → `dart compile exe` → `debian:trixie-slim`) → `registry.weyland.lab/golden-dart-shelf` |
| Observability | structured JSON logging on startup + `/metrics` (Prometheus text exposition, hello counter) |
| Toolchain | `dart:stable` (SDK 3.13+, Debian 13 trixie); root marker `pubspec.yaml`; test glob `*_test.dart` |

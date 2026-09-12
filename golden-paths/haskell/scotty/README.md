# Golden path — Haskell / Scotty

The blessed paved-road **Haskell** service, built on [Scotty](https://hackage.haskell.org/package/scotty)
(lighter + faster to build than Servant) + [aeson](https://hackage.haskell.org/package/aeson).
**Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `GET /health` · `/ready` ·
`/metrics` · `/hello`. Binds `0.0.0.0:8080`.

## Run it (locally)

```
cabal run golden-haskell-scotty        # then: curl localhost:8080/hello -> {"service":"golden-haskell-scotty","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
cabal test                             # the `contract` suite: 9 checks pass; the selfcheck is NOT built (exit 0)
cabal test selfcheck -fselfcheck       # the deliberate failure — builds + runs + exits non-zero (proves the lane propagates)
hlint src app test                     # scan lane — clean
```

**selfcheck gotcha (cabal):** `cabal test` runs *every buildable* test-suite in the package, so a
plain second suite would fail the everyday run. The `selfcheck` suite is gated behind a **manual cabal
flag** (`flag selfcheck`, `default: False`) with `if !flag(selfcheck) { buildable: False }`, so a bare
`cabal test` cannot build or run it — the everyday suite is green. The lane self-check turns the flag
on **and names the suite** — `cabal test selfcheck -fselfcheck` — which is the only way the deliberate
failure genuinely executes and exits non-zero. (Naming the suite matters: with the flag on, both suites
are buildable, so a bare `cabal test -fselfcheck` would also run `contract`.)

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

Works as the Python FastAPI reference — see [../../python/fastapi/README.md](../../python/fastapi/README.md)
and `scripts/run-golden-path-jobs.sh` (reads `.smoke`). buildkit builds
`registry.weyland.lab/golden-haskell-scotty`, the run-to-completion Job starts it, asserts `/ready` +
`/hello`'s known payload via `smoke.sh`, exits 0, and is deleted. Never a Deployment.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh haskell/scotty <your-service>
```

Rewrites `serviceName` (`src/Lib.hs`), drops the selfcheck suite, fills the onboarding declaration
below, and gives you a runnable, gate-passing starting point. The declaration is what makes the
scaffolded service pass the onboarding gates (B154/B155) **by construction** — fill each `<...>` and
the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
# Scotty serves no native OpenAPI, so author the spec file by hand (there is no /openapi.json
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
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (routes in `src/Lib.hs`, served by `app/Main.hs` via `scottyOpts`, `setHost "*"` → 0.0.0.0) |
| Self-test | `test/Spec.hs` — pure payload-builder checks (order-independent `Value` equality) + the live WAI app over `Network.Wai.Test`/hspec-wai; `test/Selfcheck.hs` (deliberate fail, gated by `flag selfcheck`) |
| Build | multi-stage non-root `Dockerfile` (`haskell:9.8` `cabal build` → `debian:bookworm-slim` + libgmp10, `libffi.so.7` carried from build stage) → `registry.weyland.lab/golden-haskell-scotty` |
| Observability | structured JSON log line on startup + `/metrics` (Prometheus text 0.0.4, hello counter over an `IORef`) |
| Toolchain | `haskell:9.8` (GHC 9.8.4, cabal 3.14, Debian 11 bullseye); root marker `*.cabal`; test glob `test/*.hs`; `cabal.project.freeze` committed for reproducibility |

## Lane-wiring facts (for `run-lang-tests.sh` / `run-lang-scan.sh` / `.woodpecker.yml`)

- **Runner image**: `haskell:9.8`
- **Root marker**: `*.cabal` (this dir carries `golden-haskell-scotty.cabal`)
- **Test glob**: `test/*.hs`
- **Test command**: `cabal test contract` (or bare `cabal test`)
- **Selfcheck command**: `cabal test selfcheck -fselfcheck` (must exit non-zero)
- **Scan command**: `hlint src app test`

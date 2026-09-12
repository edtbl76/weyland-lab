# Golden path — Erlang / Cowboy

The idiomatic Erlang baseline — **Cowboy** on **ranch**, no framework ceremony. **Runnable · ephemeral ·
extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready` `/metrics`
`/hello`.

```
rebar3 eunit                    # 4 contract tests over a live Cowboy listener (ephemeral port, httpc)
rebar3 as selfcheck eunit       # the deliberate failure (proves the lane propagates → exit non-zero)
rebar3 release                  # self-contained release, bundles ERTS → _build/prod/rel/golden_cowboy
```

Layout: `rebar.config` (cowboy 2.12; `selfcheck` profile adds `selfcheck/`); `src/golden_cowboy_router.erl`
compiles the whole contract dispatch (shared by the app and the tests); `src/golden_cowboy_handler.erl`
serves the four endpoints; `src/golden_cowboy_app.erl` starts Cowboy on `$PORT` (default 8080).
Metrics = a hand-rolled Prometheus text endpoint backed by an OTP `counters` array. The
deliberately-failing test lives in `selfcheck/`, compiled only under the `selfcheck` profile (a normal
`rebar3 eunit` never sees it — mirrors the go exemplar's `deliberate` build tag). The image is a
`rebar3 release` (self-contained, bundles ERTS) on a `debian-slim` runtime.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh erlang/cowboy <your-service>
```

Rewrites the service name, drops the selfcheck, and prints the onboarding declaration below. The
declaration is what makes the scaffolded service pass the onboarding gates (B154/B155) **by
construction** — fill each `<...>` and the guards go green:

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

## Ephemeral Job + the onboarding declaration

**Ephemeral Job + scaffolding** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`).

## Contract compliance

| Facet | This golden path |
|---|---|
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (`golden_cowboy_handler`, `:8080`) |
| Self-test | `test/golden_cowboy_tests.erl` (4 tests over a live listener) + `selfcheck/` (deliberate fail, `selfcheck` profile only) |
| Build | multi-stage non-root `Dockerfile` (`erlang:27` → `debian:bookworm-slim`) → `registry.weyland.lab/golden-erlang-cowboy` |
| Observability | structured `logger` output + `/metrics` (hand-rolled Prometheus counter over OTP `counters`) |

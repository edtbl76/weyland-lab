# Golden path — Lua / OpenResty

The blessed paved-road OpenResty service (nginx + LuaJIT, `content_by_lua_block`). **Runnable · ephemeral ·
extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `GET /health` · `/ready` ·
`/metrics` · `/hello`.

Layout: `nginx.conf` wires four `location` blocks onto the pure handlers via `content_by_lua_block`;
`lua/handlers.lua` are the pure payload-builders (unit-testable under headless busted — busted cannot bind
nginx and `ngx` only exists inside a running worker, so these cover the payload logic and the smoke curls
the real server); `.busted` is the lane root marker + task profiles; `spec/*_spec.lua` is the suite;
`Dockerfile` builds the non-root image; `smoke.sh` + `.smoke` drive the ephemeral Job. JSON and the
Prometheus `/metrics` exposition are hand-rolled so the module stays dependency-free.

## Run it (locally, in the OpenResty image)

```
docker build -t golden-lua-openresty .
docker run --rm -p 8080:8080 golden-lua-openresty
# then: curl localhost:8080/hello -> {"service":"golden-lua-openresty","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
busted                       # 4 contract tests over the payload builders; EXCLUDES the #selfcheck tag → passes
busted --run=selfcheck       # runs ONLY the deliberate #selfcheck spec → FAILS (proves the lane propagates)
luacheck .                   # the scan lane (fail-closed): lints lua/ + spec/, clean via .luacheckrc
bash scripts/run-lang-tests.sh lua   # the CI lane discovers this golden path by the .busted marker
```

The toolchain image for the test/scan lane is an official `lua` image (or `openresty/openresty:alpine`)
with `luarocks install busted luacheck`. Test glob `spec/*_spec.lua`; root marker `.busted`.

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

`scripts/run-golden-path-jobs.sh` builds `registry.weyland.lab/golden-lua-openresty` via buildkit and
applies a run-to-completion Job (ns `golden-paths`) that runs `.smoke` (`sh smoke.sh`): it starts the
real OpenResty server, asserts `/ready` + `/hello`'s known payload, exits 0, and is deleted. Never a
Deployment.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh lua/openresty <your-service>
```

Rewrites the `golden-lua-openresty` service name, drops the selfcheck spec, and fills the onboarding
declaration below. The declaration is what makes the scaffolded service pass the onboarding gates
(B154/B155) **by construction** — fill each `<...>` and the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
- {id: <your-service>, owner: <your-service>, kind: openapi, status: published, version: "1.0",
   base: "http://<your-service>.weyland.svc:8080",
   spec: docs/api/specs/<your-service>.openapi.json, consumers: []}
```

```
# --- weyland.likec4 (add to the right zone) ---
yourServiceCamelId = component "Your Service" "<one line>"
```

OpenResty has no framework-native OpenAPI generator, so hand-author the spec at
`docs/api/specs/<your-service>.openapi.json` (the four contract routes), then run
`scripts/gen-api-contract-lock.sh` and the onboarding + API-lifecycle guards pass.

## Contract compliance

| Facet | This golden path |
|---|---|
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (nginx.conf `content_by_lua_block` → lua/handlers.lua) |
| Self-test | `spec/handlers_spec.lua` (busted over the payload builders) + `spec/selfcheck_spec.lua` (`#selfcheck` deliberate fail) |
| Build | single-stage non-root `Dockerfile` on `openresty/openresty:alpine` → `registry.weyland.lab/golden-lua-openresty` |
| Observability | nginx access log to stdout + `/metrics` (hand-rolled Prometheus text exposition) |
| API lifecycle | hand-authored OpenAPI spec captured by B155 (no framework-native generator) |

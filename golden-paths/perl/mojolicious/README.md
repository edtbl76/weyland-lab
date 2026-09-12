# Golden path — Perl / Mojolicious

The blessed paved-road **Perl** service — a Mojolicious full-app on `Mojo::Base 'Mojolicious'`.
**Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `GET /health` · `/ready` ·
`/metrics` · `/hello`. Binds `http://*:8080` (all interfaces).

## Run it (locally)

```
cpanm --installdeps .                            # installs Mojolicious (pure-Perl, no compiler)
perl script/golden_perl_mojolicious              # then: curl localhost:8080/hello
                                                 #   -> {"service":"golden-perl-mojolicious","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
prove -l                                         # 4 contract tests pass (runs t/ only); selfcheck untouched (exit 0)
prove -l selfcheck/                              # the deliberate failure — runs + exits non-zero (proves the lane propagates)
perlcritic lib script                            # scan lane — Perl::Critic (cpanm --with-develop --installdeps .)
```

`prove -l` defaults to `t/` and adds `lib/` to `@INC`; the selfcheck lives OUTSIDE `t/` (in
`selfcheck/`), so a bare `prove -l` never sees it and stays green — the failing test is reached only
by the explicit `prove -l selfcheck/` path. `Test::Mojo` drives the app **in-process** (no live
socket), so the contract tests need no port.

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

Works as the Python FastAPI reference — see [../../python/fastapi/README.md](../../python/fastapi/README.md)
and `scripts/run-golden-path-jobs.sh` (reads `.smoke`). buildkit builds
`registry.weyland.lab/golden-perl-mojolicious`, the run-to-completion Job starts it, asserts `/ready` +
`/hello`'s known payload via `smoke.sh`, exits 0, and is deleted. Never a Deployment.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh perl/mojolicious <your-service>
```

Rewrites `$SERVICE_NAME`, fills the onboarding declaration below, and gives you a runnable,
gate-passing starting point. The declaration is what makes the scaffolded service pass the onboarding
gates (B154/B155) **by construction** — fill each `<...>` and the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
# Mojolicious serves no native OpenAPI, so author the spec file by hand (there is no /openapi.json
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
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (`lib/GoldenPerlMojolicious.pm`, served by `script/golden_perl_mojolicious`) |
| Self-test | `t/contract.t` (Test::More + Test::Mojo, drives the app over all four) + `selfcheck/selfcheck.t` (deliberate fail, outside `t/`) |
| Build | multi-stage non-root `Dockerfile` (`perl:5.40` → `cpanm --installdeps` into local::lib → `perl:5.40-slim`) → `registry.weyland.lab/golden-perl-mojolicious` |
| Observability | structured JSON log line on startup + `/metrics` (Prometheus text exposition, hello counter) |
| Toolchain | `perl:5.40`; root marker `cpanfile`; test glob `*.t`; scan `perlcritic` |

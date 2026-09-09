# Golden path — Elixir / Phoenix

The flagship Elixir service template — **API-only Phoenix 1.8** (`--no-html --no-assets --no-ecto`) on
**Bandit**. **Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready` `/metrics`
`/hello`. Its lean sibling is [../plug](../plug).

```
mix deps.get && mix test                 # 4 contract tests (ConnCase through the real endpoint)
mix test --only selfcheck                 # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh elixir     # the CI lane runs this golden path as its fixture
```

Layout: standard Phoenix (`lib/golden_phoenix_web/` endpoint + router + controllers), trimmed to the
contract — `GoldenController` serves all four paths at the root scope; `config/prod.exs` drops the
generated `force_ssl` (LAN plain-HTTP canary); `config/runtime.exs` keeps the strict
`SECRET_KEY_BASE`-required prod boot (the image supplies a fixed lab value + `PHX_SERVER`). Metrics = a
hand-rolled Prometheus text endpoint. The deliberately-failing test carries `@tag :selfcheck` (excluded
in `test_helper.exs`). The image is a `mix release` (bundles ERTS) on a `debian-slim` runtime.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh elixir/phoenix <your-service>`.

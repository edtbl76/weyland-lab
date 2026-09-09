# Golden path — Elixir / Plug

The lean Elixir baseline — `Plug.Router` on **Bandit**, no framework ceremony. The lean sibling of the
[Phoenix flagship](../phoenix). **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
mix deps.get && mix test                 # 4 contract tests (router driven in-process via Plug.Test)
mix test --only selfcheck                 # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh elixir     # the CI lane runs this alongside the Phoenix fixture
```

Layout: `mix.exs` (plug + bandit + jason; credo dev-only); `lib/golden_plug/router.ex` serves the whole
contract; `lib/golden_plug/application.ex` starts Bandit on `$PORT` (8080). Metrics = a hand-rolled
Prometheus text endpoint. The deliberately-failing test carries `@tag :selfcheck` (excluded from a
normal run in `test_helper.exs`). The image is a `mix release` (self-contained, bundles ERTS) on a
`debian-slim` runtime.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh elixir/plug <your-service>`.

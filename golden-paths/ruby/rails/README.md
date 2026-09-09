# Golden path — Ruby / Rails

The flagship Ruby service template — **API-only, minimal railties** (Action Controller + routing, no
Active Record / Action View). **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`. Its lean sibling is [../sinatra](../sinatra).

```
bundle install && bundle exec rake test            # 4 contract tests (real router + controllers)
bundle exec rake test:selfcheck                    # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh ruby                # the CI lane runs this golden path as its fixture
```

Layout: `Gemfile` (rails + puma; rake + rubocop in the test group); `config/` the minimal boot
(`application.rb` sets `api_only`, a fixed lab `secret_key_base`, stdout logging, and cleared host
allowlist — no per-environment files needed); `app/controllers/golden_controller.rb` serves the whole
contract; `config.ru` is the puma/Rack entrypoint. Metrics = a hand-rolled Prometheus text endpoint at
`/metrics` (a real service swaps in the `prometheus-client` gem). The deliberately-failing test lives in
`selfcheck/` (outside the `test` rake glob) so a normal run never collects it.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh ruby/rails <your-service>`.

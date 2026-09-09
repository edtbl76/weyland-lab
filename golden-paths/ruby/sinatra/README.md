# Golden path — Ruby / Sinatra

The idiomatic Ruby micro-framework baseline — the **lean sibling** of the [Rails flagship](../rails).
**Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready` `/metrics`
`/hello`.

```
bundle install && bundle exec rake test            # 4 contract tests (app driven in-process via rack-test)
bundle exec rake test:selfcheck                    # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh ruby                # the CI lane runs this alongside the Rails fixture
```

Layout: `Gemfile` (sinatra + puma + rackup; rack-test + minitest + rubocop in the test group);
`app.rb` is a modular `Sinatra::Base` subclass so the same object serves (via `config.ru`) and is
tested in-process; host authorization is cleared (`permitted_hosts: []`) so the LAN canary accepts any
Host. Metrics = a hand-rolled Prometheus text endpoint at `/metrics`. The deliberately-failing test
lives in `selfcheck/` (outside the `test` rake glob) so a normal run never collects it.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh ruby/sinatra <your-service>`.

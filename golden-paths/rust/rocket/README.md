# Golden path — Rust / rocket

Blessed paved-road rocket service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
cargo test                                 # 4 contract tests
cargo test -- --ignored                    # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh rust        # the CI lane runs this golden path
```

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh rust/rocket <your-service>`.

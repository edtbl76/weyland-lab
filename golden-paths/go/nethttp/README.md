# Golden path — Go / nethttp

Blessed paved-road nethttp service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
go test ./...                              # 4 contract tests (coverage profile written)
go test -tags deliberate -run DeliberateFailure ./...   # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh go          # the CI lane runs this golden path
```

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh go/nethttp <your-service>`.

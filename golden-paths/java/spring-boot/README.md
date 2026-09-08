# Golden path — Java / spring-boot

Blessed paved-road spring-boot service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`. Verified via `mvn test` (4 tests + a selfcheck profile).

```
mvn test                                   # 4 contract tests (selfcheck excluded)
mvn -Pselfcheck test                       # runs ONLY the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh java        # the CI lane runs this golden path
```

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) for the applications.yaml / apis.yaml /
LikeC4 template a scaffolded service fills, and `scripts/run-golden-path-jobs.sh` (reads `.smoke`).
Scaffold: `scripts/new-service.sh java/spring-boot <your-service>`.

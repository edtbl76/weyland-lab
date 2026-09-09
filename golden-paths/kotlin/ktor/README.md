# Golden path — Kotlin / Ktor

Blessed paved-road Ktor service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
gradle test                          # 4 contract tests (Ktor testApplication, in-process)
gradle test -Pselfcheck              # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh kotlin   # the CI lane runs this golden path
```

Layout: `build.gradle.kts` + `settings.gradle.kts` (Gradle Kotlin DSL; shadow plugin → a fat
`*-all.jar` → `java -jar app.jar`); `src/main/kotlin/Application.kt` (embedded Netty, the routes);
`src/test/kotlin/` (Ktor `testApplication` + a `@Tag("selfcheck")` deliberate fail). Metrics via
`ktor-server-metrics-micrometer` + a Prometheus registry scraped at `/metrics`.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh kotlin/ktor <your-service>`.

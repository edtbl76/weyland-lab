# Golden path — Scala / http4s

Blessed paved-road http4s service (cats-effect + Ember). **Runnable · ephemeral · extendable.** Conforms
to the golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)):
`/health` `/ready` `/metrics` `/hello`.

```
sbt test                       # 4 contract tests (routes driven in-process, no server)
sbt -Dselfcheck=true test      # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh scala   # the CI lane runs this golden path
```

Layout: `build.sbt` + `project/` (sbt · native-packager → a staged `bin/` launcher, not a fat jar);
`src/main/scala/Main.scala` (http4s Ember server + the routes, `IOApp.Simple`); `src/test/scala/`
(munit-cats-effect, routes run in-process + a `*Deliberate*` selfcheck). Responses are plain JSON
strings (no circe); metrics via the Prometheus Java client scraped at `/metrics`.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh scala/http4s <your-service>`.

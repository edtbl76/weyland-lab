# Golden path — Clojure / Ring

The lean Clojure baseline — a **bare Ring handler** dispatching on `:uri`, no routing library, served by
**Jetty**. The lean sibling of the [Compojure flagship](../compojure). **Runnable · ephemeral ·
extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready` `/metrics`
`/hello`.

```
lein test                                 # 4 contract tests (handler driven in-process via ring-mock)
lein test :selfcheck                       # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh clojure     # the CI lane runs this alongside the Compojure fixture
```

Layout: `project.clj` (Leiningen — ring core + jetty adapter + cheshire; ring-mock dev-only); clj-kondo
lints it in the scan lane; `src/golden/core.clj` is a single handler that `case`s on `:uri` and exposes `-main` (Jetty on
`$PORT`, 8080). Metrics = a hand-rolled Prometheus text endpoint. The deliberately-failing test carries
`^:selfcheck`, excluded by the `:default` test-selector. The image is a `lein uberjar` on a
`temurin-21-jre` runtime, run non-root.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh clojure/ring <your-service>`.

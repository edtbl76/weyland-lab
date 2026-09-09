# Golden path — Clojure / Ring + Compojure

The flagship Clojure service template — the idiomatic **Compojure** routing DSL over **Ring**, served by
**Jetty**. **Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready` `/metrics`
`/hello`. Its lean sibling is [../ring](../ring) (bare Ring handler, no routing lib).

```
lein test                                 # 4 contract tests (handler driven in-process via ring-mock)
lein test :selfcheck                       # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh clojure     # the CI lane runs this golden path as its fixture
```

Layout: `project.clj` (Leiningen — ring + compojure + cheshire; ring-mock dev-only); clj-kondo lints it
in the scan lane;
`src/golden/core.clj` serves the whole contract and exposes `-main` (Jetty on `$PORT`, 8080). Metrics =
a hand-rolled Prometheus text endpoint. The deliberately-failing test carries `^:selfcheck`, excluded by
the `:default` test-selector. The image is a `lein uberjar` on a `temurin-21-jre` runtime, run non-root.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh clojure/compojure <your-service>`.

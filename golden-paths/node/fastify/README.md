# Golden path — Node / Fastify

Blessed paved-road Fastify service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
npm install && node --test                 # 4 contract tests (node:test + fastify.inject(), 100% coverage)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh javascript   # the CI lane runs this golden path
```

Dependency-light on purpose: no test-runner and no supertest — the tests drive the app through
`fastify.inject()` (in-memory, no port), so `fastify` + `prom-client` are the only deps. `/metrics` is
`prom-client` exposition (`golden_hello_requests_total`); the server binds `0.0.0.0:8080`. The selfcheck
is named `*.selfcheck.js` so `node --test`'s default `*.test.*` discovery never collects it.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh node/fastify <your-service>`.

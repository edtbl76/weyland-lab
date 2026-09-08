# Golden path — Node / Express

Blessed paved-road Express service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
npm install && npm test                    # 4 contract tests (jest + supertest, 100% coverage)
npm run test:selfcheck                     # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh javascript  # the CI lane runs this golden path
```

`/metrics` is `prom-client` exposition; the demo counter is `golden_hello_requests_total`. The server
binds `0.0.0.0:8080` (`src/server.js`); `createApp()` is exported so the tests exercise the real routes
over supertest without a port.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh node/express <your-service>`.

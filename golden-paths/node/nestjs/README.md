# Golden path — Node / NestJS

Blessed paved-road NestJS service (TypeScript). **Runnable · ephemeral · extendable.** Conforms to the
golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health`
`/ready` `/metrics` `/hello`.

```
npm install && npm test                    # 4 contract tests (@nestjs/testing + supertest, ts-jest)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && node dist/main.js          # tsc -> dist/main.js, then serve on :8080
bash scripts/run-lang-tests.sh typescript   # the CI lane runs this golden path
```

`AppController` carries the four routes; `/metrics` returns `prom-client` exposition
(`golden_hello_requests_total`). The test file is named `app.test.ts` (not Nest's usual `*.spec.ts`) so
the lane's `*.test.ts` discovery glob finds this project's root; the Dockerfile builds `dist/` and runs
`node dist/main.js` (non-root, binds `0.0.0.0:8080`). Coverage is measured on the controller/module;
Nest's decorator metadata is counted but not unit-testable, so the baseline sits below 100% by design.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh node/nestjs <your-service>`.

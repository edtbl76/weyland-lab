# Golden path — Frontend / Astro

Blessed paved-road Astro service (SSR via `@astrojs/node`). **Runnable · ephemeral · extendable.**
Satisfies the frontend adaptation of the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): the demo page SSR-renders the
greeting, and `/health` `/ready` `/metrics` `/hello` are real Astro endpoints.

```
npm install && npm test                    # 5 contract tests (jest + ts-jest, 100% coverage)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && node ./dist/server/entry.mjs   # astro build (SSR) -> serve (HOST/PORT env)
bash scripts/run-lang-tests.sh react        # the CI lane runs this golden path
```

`output: 'server'` + the standalone node adapter give a real server, so the endpoints and the
SSR-rendered demo route both come from Astro (the smoke greps `/hello`'s payload AND the greeting in
`/`). jest can't transform `.astro`, so the lane tests the shared `greeting` module and the endpoint
handlers directly (plain functions returning a `Response`); `/metrics` exposes
`golden_hello_requests_total`.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh frontend/astro <your-service>`.

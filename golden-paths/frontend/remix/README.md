# Golden path — Frontend / Remix

Blessed paved-road Remix service (React SSR via Remix + Vite). **Runnable · ephemeral · extendable.**
Satisfies the frontend adaptation of the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): the `_index` route SSR-renders
the greeting, and `/health` `/ready` `/metrics` `/hello` are resource routes.

```
npm install && npm test                    # 3 contract tests (jest + testing-library, 100% coverage)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && PORT=8080 npm start        # remix vite:build, then remix-serve
bash scripts/run-lang-tests.sh react        # the CI lane runs this golden path
```

Resource routes return JSON via Remix's `json()` helper (the server runtime's `Response` has no static
`.json()`); `/metrics` exposes `golden_hello_requests_total`. The jest lane tests the pure `Hello`
component + the shared greeting; the resource-route loaders and SSR page are smoke-verified. `Hello`
renders one template literal (not `hello, {name}`) so the SSR HTML carries the greeting contiguously.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh frontend/remix <your-service>`.

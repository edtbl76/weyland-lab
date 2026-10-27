# Golden path — Frontend / React Router

Blessed paved-road React SSR service on **React Router 8 framework mode** + Vite. **Runnable · ephemeral ·
extendable.** Satisfies the frontend adaptation of the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): the `_index` route SSR-renders
the greeting, and `/health` `/ready` `/metrics` `/hello` are resource routes.

**Was Remix until 2026-10-27.** Remix v2 reached end of life and its successor is React Router framework mode; 11 of
the 22 advisories against the Remix packages had no fix on v2. The migration: `@remix-run/*` became `react-router` +
`@react-router/{node,serve,dev,fs-routes}`, React 18 → 19 (React Router 8 needs 19.2.7+), vite 6 → 8,
`app/routes.ts` (`flatRoutes()`, the same `app/routes/` file convention) and `react-router.config.ts` (SSR on) were
added, and Remix's `json()` helper became the standard `Response.json()`.

```
npm install && npm test                    # 3 contract tests (jest + testing-library, 100% coverage)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && PORT=8080 npm start        # react-router build, then react-router-serve
bash scripts/run-lang-tests.sh react        # the CI lane runs this golden path
```

Resource routes return JSON via `Response.json()`; `/metrics` exposes `golden_hello_requests_total`. The jest lane
tests the pure `Hello` component + the shared greeting; the resource-route loaders and SSR page are smoke-verified.
`Hello` renders one template literal (not `hello, {name}`) so the SSR HTML carries the greeting contiguously.
`react-router typegen` writes route types to `.react-router/` (ignored by git and the image build).

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh frontend/react-router <your-service>`.

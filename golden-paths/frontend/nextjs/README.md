# Golden path — Frontend / Next.js

Blessed paved-road Next.js service (App Router, React SSR). **Runnable · ephemeral · extendable.**
Satisfies the frontend adaptation of the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): the demo page SSR-renders the
greeting, and `/health` `/ready` `/metrics` `/hello` are route handlers.

```
npm install && npm test                    # 3 contract tests (jest + testing-library, 100% coverage)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && node .next/standalone/server.js   # next build (standalone) -> serve on :8080
bash scripts/run-lang-tests.sh react        # the CI lane runs this golden path
```

Route handlers are `export const dynamic = 'force-dynamic'` so they run per-request (never statically
prerendered — required for `/metrics` and the `/hello` counter). `output: 'standalone'` emits a
self-contained `server.js`; the image runs `node server.js` (non-root, `HOSTNAME=0.0.0.0 PORT=8080`).
The jest lane tests the pure `Hello` component + the shared greeting; the route handlers and SSR page
are smoke-verified. `/metrics` exposes `golden_hello_requests_total`.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh frontend/nextjs <your-service>`.

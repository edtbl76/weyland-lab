# Golden path — Frontend / Vite+React

Blessed paved-road Vite + React SPA. **Runnable · ephemeral · extendable.** Satisfies the frontend
adaptation of the golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)):
the demo route renders `<Hello/>`, and the contract endpoints `/health` `/ready` `/metrics` `/hello`
are served by a tiny stdlib static server (the "sidecar route" the adapted contract allows).

```
npm install && npm test                    # 3 contract tests (jest + testing-library, 100% coverage)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && node server.mjs            # vite build -> dist/, then serve on :8080
bash scripts/run-lang-tests.sh react        # the CI lane runs this golden path
```

A pure SPA has no server of its own, so `server.mjs` (stdlib `http` + `prom-client`, no express)
serves `dist/` with an SPA fallback and answers the four contract endpoints; the SPA renders the
greeting client-side, so the smoke asserts `/hello`'s JSON payload plus the served bundle. `/metrics`
exposes `golden_hello_requests_total`.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference —
see [../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh frontend/vite-react <your-service>`.

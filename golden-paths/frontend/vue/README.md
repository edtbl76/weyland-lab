# Golden path — Frontend / Vue3 + Vite

Blessed paved-road Vue 3 + Vite SPA. **Runnable · ephemeral · extendable.** Satisfies the frontend
adaptation of the golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)):
the demo route renders `<Hello/>`, and the contract endpoints `/health` `/ready` `/metrics` `/hello`
are served by a tiny stdlib static server (the "sidecar route" the adapted contract allows).

```
npm install && npm test                    # 3 contract tests (vitest + @vue/test-utils)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && node server.mjs            # vite build -> dist/, then serve on :8080
bash scripts/run-lang-tests.sh react        # a node lane discovers + runs this golden path
```

Reuses the estate's existing node lanes — no net-new toolchain or runner image. A pure SPA has no
server of its own, so `server.mjs` (stdlib `http` + `prom-client`, no express) serves `dist/` with an
SPA fallback and answers the four contract endpoints; the SPA renders the greeting client-side, so the
smoke asserts `/hello`'s JSON payload plus the served bundle (whose `<title>` carries the service name).
`/metrics` exposes `golden_hello_requests_total`. The `*.vue` shim in `src/vite-env.d.ts` lets the
scan lane's plain `tsc` resolve SFC imports.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../vite-react/README.md](../vite-react/README.md) and `scripts/run-golden-path-jobs.sh` (reads
`.smoke`). Scaffold a real service: `scripts/new-service.sh frontend/vue <your-service>`.

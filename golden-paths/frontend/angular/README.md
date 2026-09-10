# Golden path — Frontend / Angular

Blessed paved-road Angular 19 SPA. **Runnable · ephemeral · extendable.** Satisfies the frontend
adaptation of the golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)):
the demo route renders the greeting, and the contract endpoints `/health` `/ready` `/metrics` `/hello`
are served by a tiny stdlib static server (the "sidecar route" the adapted contract allows).

```
npm install && npm test                    # 3 contract tests (jest, headless, on the pure greeting logic)
npm run test:selfcheck                      # the deliberate failure (proves the lane propagates)
npm run build && node server.mjs            # ng build -> dist/.../browser, then serve on :8080
bash scripts/run-lang-tests.sh react        # a node lane discovers + runs this golden path
```

Reuses the estate's existing node lanes — no net-new toolchain or runner image. **The default `ng test`
(Karma + a real browser) is replaced with headless jest** over the pure `greeting()` logic, because the
node lane runs in `node:24-alpine` with no browser; the built Angular app itself is proven by the curl
smoke. A pure SPA has no server of its own, so `server.mjs` (stdlib `http` + `prom-client`, no express)
serves `dist/golden-frontend-angular/browser/` with an SPA fallback and answers the four endpoints; the
`<title>` carries the service name for the smoke's demo-route check. `/metrics` exposes
`golden_hello_requests_total`.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../vite-react/README.md](../vite-react/README.md) and `scripts/run-golden-path-jobs.sh` (reads
`.smoke`). Scaffold a real service: `scripts/new-service.sh frontend/angular <your-service>`.

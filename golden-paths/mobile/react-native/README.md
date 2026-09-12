# Golden path — Mobile / React Native (Expo)

Blessed paved-road **Expo** (React Native) app. **Buildable · testable · extendable.** Satisfies the
**B164 mobile ADAPTED contract** ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)).

## A mobile app is a CLIENT, not an HTTP service

The framework-agnostic golden-path contract (`/health` `/ready` `/metrics` `/hello` + a Dockerfile +
a run-to-completion k8s Job) assumes a **server**. A mobile app has none of that — it ships to a device,
not to the cluster. So this path deliberately has:

- **NO** `/health` `/ready` `/metrics` `/hello` HTTP endpoints
- **NO** `Dockerfile` (there is no server image to build or run)
- **NO** run-to-completion k8s Job / `.smoke` (nothing to serve in-cluster; `run-golden-path-jobs.sh`
  discovers by Dockerfile, so it correctly skips this path)

Instead the **adapted contract** is four things, all Linux-CI-buildable:

1. **App skeleton that bundles + builds** — an Expo app (`App.tsx` → `<Hello/>`), service-name token
   `golden-react-native`.
2. **A test that a component renders the known payload** — `test/Hello.test.tsx` asserts `<Hello/>`
   renders `hello, weyland` via **jest-expo** + **@testing-library/react-native**. This is the
   `/hello`-equivalent: the greeting is rendered **on-screen**, not served over HTTP.
3. **A selfcheck deliberately-failing test** — `selfcheck/deliberate.test.tsx`, excluded from a normal
   `npm test` and run only under `npm run test:selfcheck`, proving the lane propagates failure.
4. **A headless bundle/render smoke** — `npm run bundle` (`expo export --platform web`) proves the app
   actually bundles/builds. This replaces the image-build + curl smoke that a server path uses.

```
npm install && npm test        # 4 contract tests (jest-expo + testing-library-react-native)
npm run test:selfcheck         # the deliberate failure (proves the lane propagates) — exits non-zero
npm run bundle                 # expo export --platform web -> dist/  (the headless bundle smoke)
npm run lint                   # eslint (the scan lane)
```

Verified end-to-end in the CI `node:24` image on rogueone: `npm test` green, `npm run test:selfcheck`
non-zero, `npm run bundle` exit 0.

## /hello-equivalent payload

The known payload is the greeting string **`hello, weyland`**, rendered by `<Hello/>` and asserted by
the contract test. The service-name token is **`golden-react-native`** (`SERVICE_NAME` in `src/Hello.tsx`,
`expo.name`/`slug` in `app.json`, and the package `name`).

## Onboarding declaration

A mobile client is not deployed to the cluster, so the standard onboarding facets that assume a running
in-cluster service do **not** apply:

- `applications.yaml` — a mobile client has no `deployed`/`metrics`/`ingress` in-cluster surface; it is
  a build artifact (an app bundle / store submission), not a k8s workload. Declare it, if at all, as a
  non-deployed component (`deployed: false`) with no metrics/ingress rows.
- `apis.yaml` — this path exposes **no** HTTP API; it is a consumer of APIs, so it owns no `apis.yaml`
  entry. (A real app scaffolded from it declares the backend APIs it *consumes*, not one it serves.)
- LikeC4 — model it as a client/external actor element, not a deployed service node.

## Lane isolation (IMPORTANT)

The four web-node lanes (`typescript` / `javascript` / `react` / `nextjs`) share **one repo-wide test
glob** (`*.test.{js,ts,jsx,tsx}` + nearest `package.json` root marker). This RN app carries both, so it
would be swept into web-react/jsdom discovery unless the runner distinguishes it. The RN app is
distinguishable by the **`expo` / `react-native` dependency in `package.json`** — that capability marker
(mirroring how `scan_node` treats `tsc`/`next` as capability-driven, not lane-driven) is how a dedicated
`mobile`/`react-native` lane should claim it and the web-node lanes should skip it. See the build report
for the exact runner-wiring recommendation.

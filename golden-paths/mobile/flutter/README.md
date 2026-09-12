# Golden path — MOBILE Flutter client

The blessed paved-road **mobile Flutter client**. **Runnable · ephemeral · extendable.**

## Mobile contract note (why this is NOT the service contract)

A mobile app is a **CLIENT, not an HTTP service.** It has no listening socket, so the framework-agnostic
service contract in [docs/design/golden-paths.md](../../../docs/design/golden-paths.md) does **not** apply
here — there are **no `/health` `/ready` `/metrics` `/hello` endpoints, NO Dockerfile, and NO
run-to-completion k8s Job** (there is nothing to `curl`, and a client is not "served" on the platform).

Instead this path satisfies the **B164 adapted mobile contract**, four facets:

| Facet | This golden path |
|---|---|
| **Bundles + builds** | a real Flutter app (`pubspec.yaml` + `lib/main.dart`) that renders the known payload `hello, weyland`; service-name token `golden-flutter`. |
| **Widget test** | `test/widget_test.dart` — `flutter test` renders the app and asserts the greeting `hello, weyland` is on screen. |
| **selfcheck** | `test/selfcheck_test.dart` — a deliberately-failing test, tagged `selfcheck`, **excluded from a normal `flutter test`** and run only under a flag. Proves the lane propagates failure. |
| **Headless build smoke** | `flutter build web` — a headless, Linux-buildable bundle of the app (the CI-verifiable proxy for a device build). |

## Test it (the CI lane runs exactly this)

```
flutter pub get                            # resolve deps first (fetches the flutter SDK packages)
flutter test                               # widget test passes; selfcheck is SKIPPED (exit 0)
flutter test -t selfcheck --run-skipped    # the deliberate failure — runs + exits non-zero
flutter analyze                            # scan lane — clean (dart analyze also works)
```

**selfcheck gotcha (package:test, same as dart/shelf):** you cannot both exclude a tag from a bare
`flutter test` via `dart_test.yaml` AND run it via a bare `flutter test -t selfcheck`. A `skip:` tag
config makes `-t selfcheck` report *"All tests skipped"* (exit 0 — a fail-open trap); `exclude_tags`
makes it report *"No tests match"* (non-zero, but the failing test never runs, proving nothing). The
`--run-skipped` flag is what forces the skip-tagged selfcheck to genuinely execute and fail. See
`dart_test.yaml`.

## Build smoke (headless, Linux-buildable)

```
flutter build web        # -> build/web/ (index.html + flutter_bootstrap.js + main.dart.js); exit 0
```

`flutter build web` is the CI build smoke: a mobile client can't be `curl`ed on the platform, and iOS/
Android device builds are hardware/toolchain-gated (the iOS Swift path stays parked — B164 workstream-1),
so the **Linux-buildable web target** is the headless proxy that proves the app bundles + compiles. The
canonical `web/` scaffolding (index.html, manifest.json, icons) is committed so the build is
self-contained — no `flutter create` step needed in CI.

## Lane isolation — keeping Flutter OFF the server-Dart lane

The `dart` service lane resolves its fixture to `golden-paths/dart/shelf` (marker `pubspec.yaml`, test
glob `*_test.dart`) and then **discovers real Dart projects repo-wide by the same marker + glob**
(`scripts/run-lang-tests.sh` `discover_roots`). A Flutter app **also** carries `pubspec.yaml` + a
`test/*_test.dart`, so left alone it would be discovered by the dart lane and run under **`dart test`** —
which is wrong: a Flutter package needs **`flutter test`** (and `dart pub get` in a Flutter package
errors, "Flutter users should run `flutter pub get`"). Two mechanisms distinguish them; use **both** so
the split is robust:

1. **Intrinsic in-tree signal (already present in this path).** A Flutter `pubspec.yaml` carries a
   top-level **`flutter:`** key and a **`sdk: flutter`** dependency; a server-Dart pubspec (dart/shelf)
   carries neither. That is the natural discriminator a dispatcher keys on to route a `pubspec.yaml`
   root to `flutter test` vs `dart test`.
2. **`is_excluded` path (the shared-file wiring a follow-up commit applies).** Add
   `*/golden-paths/mobile/*` to `is_excluded()` in **both** `scripts/run-lang-tests.sh` and
   `scripts/run-lang-scan.sh` — exactly the precedent already used for `*/selfcheck/*` and
   `*/eval/coding-agents/*`. That keeps the entire mobile tree out of every existing language lane's
   discovery, so the dart lane never sees this app. The mobile Flutter lane is then a **net-new lane**
   (runner `flutter`, test glob `*_test.dart`, root marker `pubspec.yaml`, selfcheck
   `flutter test -t selfcheck --run-skipped`, scan `flutter analyze`), plus a `.woodpecker.yml`
   `test-flutter` / `scan-flutter` step on the `ghcr.io/cirruslabs/flutter:stable` image.

> This golden path deliberately does **not** edit those shared files; it carries signal (1) so whichever
> mechanism the wiring commit chooses, the discriminator already exists in-tree.

## Scaffold a REAL app FROM this

```
scripts/new-service.sh mobile/flutter <your-app>
```

Rewrites the `serviceName` token (`golden-flutter`), keeps the widget test, and drops the selfcheck.
Because a mobile client is not deployed as an in-cluster service, its onboarding declaration is a
**client** entry, not a `deployed`/`ingress`/`apis.yaml` service entry:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
# A mobile CLIENT: not deployed in-cluster, exposes no metrics endpoint, has no ingress or API of
# its own. It is a consumer of platform APIs, declared for the app lens / catalog only.
- {key: <your-app>, deployed: false, metrics: false, ingress: false, name: <Your App>,
   group: <clients|mobile>, datahub_application: false, owns: [], capabilities: [mobile-client],
   likec4: <yourAppCamelId>, port_component: <your-app>,
   description: "<one line> (Flutter mobile client)"}
```

```
# --- weyland.likec4 (add to the right zone) ---
yourAppCamelId = component "Your App" "<one line> (Flutter mobile client)"
```

There is **no `apis.yaml` entry** — a client publishes no API. It consumes them; record any dependency
as a LikeC4 relationship from `yourAppCamelId` to the API it calls.

## Contract compliance (B164 adapted mobile contract)

| Facet | This golden path |
|---|---|
| Bundles + builds | `lib/main.dart` renders `hello, weyland` (token `golden-flutter`); `flutter build web` → `build/web/` |
| Widget test | `test/widget_test.dart` (`flutter test`, asserts the greeting renders) |
| selfcheck | `test/selfcheck_test.dart` (deliberate fail, `@Tags(['selfcheck'])`, `dart_test.yaml` skip + `--run-skipped`) |
| Build smoke | `flutter build web` (headless, Linux-buildable) |
| Scan | `flutter analyze` (or `dart analyze`); `analysis_options.yaml` = `package:flutter_lints/flutter.yaml` |
| Toolchain | `ghcr.io/cirruslabs/flutter:stable` (Flutter 3.44 / Dart 3.12); root marker `pubspec.yaml`; test glob `*_test.dart` |
| NOT present | no HTTP endpoints, no Dockerfile, no k8s Job — a mobile client is not a served service |

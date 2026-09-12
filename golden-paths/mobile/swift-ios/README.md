# Golden path — Swift / iOS (SwiftUI) · MOBILE ADAPTED contract

The blessed paved-road **Swift / iOS (SwiftUI)** mobile client. This is the **mobile ADAPTED
variant** of the golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)):
a **CLIENT app, not a server** — so there are **no HTTP endpoints, no Dockerfile, no k8s Job**.
What a mobile golden path proves is its **presentation logic** and its test lane.

The lab is **$0, Linux-only** — it has **no macOS/Xcode runner**, and SwiftUI/UIKit only compile
under Xcode/macOS. So the app is **split** so the maximum is Linux-verifiable:

- **`Greeting`** (`Sources/Greeting/Greeting.swift`) — the pure presentation LOGIC, **Foundation
  only** (no `import SwiftUI`, no `import UIKit`). It produces the display string `hello, weyland`
  and the service token `golden-swift-ios`. **Built and tested on Linux with `swift test`.**
- **`App`** (`Sources/App/*.swift`) — the SwiftUI `View` + iOS `@main App` entry, authored but
  **PARKED** behind `#if canImport(SwiftUI)`. On Linux the UI reduces to nothing (the target still
  builds); on macOS/Xcode it renders `GreetingViewModel.displayText`.

## What is verified on Linux vs. parked for the iOS hardware gate

| Piece | Status | How |
|---|---|---|
| `Sources/Greeting/Greeting.swift` (pure view-model logic) | **✅ Linux-verified** | `swift build` + `swift test` in `swift:6.0` |
| `Tests/AppTests/GreetingTests.swift` (5 contract tests) | **✅ Linux-verified** | `swift test` — all pass |
| `Tests/SelfCheckTests/SelfCheckTests.swift` (deliberate fail) | **✅ Linux-verified** | `GOLDEN_SELFCHECK=1 swift test --filter SelfCheckTests` → non-zero |
| `Sources/App/ContentView.swift` (SwiftUI `View`) | **⏸ PARKED — iOS hardware gate** | needs macOS + Xcode; `#if canImport(SwiftUI)` excludes it on Linux |
| `Sources/App/GoldenSwiftIOSApp.swift` (`@main App`) | **⏸ PARKED — iOS hardware gate** | needs macOS + Xcode |
| `.xcodeproj` generation · simulator run · UI/snapshot test | **⏸ PARKED — iOS hardware gate** | no macOS/Xcode runner in a $0 Linux lab |

The Linux CI proves the logic the parked UI binds to; the UI itself is authored, compilable-under-Xcode,
and waits for a macOS runner. That is the maximum a Linux lab can honestly claim.

## Test it (the CI swift lane runs exactly this)

```
swift test                                              # Greeting logic (AppTests, 5) pass; SelfCheckTests skips
GOLDEN_SELFCHECK=1 swift test --filter SelfCheckTests   # the deliberate failure (proves the lane propagates)
swift format lint --recursive Sources Tests             # scan (advisory style findings; exits 0)
```

Verified in Docker on rogueone:

```
docker run --rm -v "$PWD/golden-paths/mobile/swift-ios:/w" -w /w swift:6.0 swift test           # exit 0, 5 pass, 1 skipped
docker run --rm -e GOLDEN_SELFCHECK=1 -v "$PWD/golden-paths/mobile/swift-ios:/w" -w /w swift:6.0 \
    swift test --filter SelfCheckTests                                                          # exit 1 (deliberate)
docker run --rm -v "$PWD/golden-paths/mobile/swift-ios:/w" -w /w swift:6.0 swift build          # exit 0 (guarded SwiftUI excluded)
```

The selfcheck lives in a second test target (`SelfCheckTests`). A bare `swift test` runs it too, so
its `XCTFail` is gated behind `GOLDEN_SELFCHECK=1` and **skipped** otherwise — the bare run is all
green. The lane surfaces the failure by setting that env var and filtering to the target. This
mirrors the sibling server-side [`swift/vapor`](../../swift/vapor/README.md) path exactly.

## Isolation from the server-side `swift/vapor` lane

Both this package and `golden-paths/swift/vapor` sit under the **one `swift` test/scan lane** and
carry the **same marker (`Package.swift`) + the same test glob (`*Tests.swift`)** — the runner does
**not** (and need not) tell them apart by framework:

- **Both correctly just run `swift test`.** `run-lang-tests.sh` runs each in its **own directory**
  (`cd "$dir" && swift test`), so there is no cross-contamination — a SwiftPM package's `swift test`
  is the right invocation for either. `vapor`'s runs XCTVapor over HTTP; this one runs the
  Foundation-only `Greeting` tests. The selfcheck (`--filter SelfCheckTests`) and scan
  (`swift format lint --recursive Sources Tests`) apply cleanly to both.
- **`vapor` is the lane FIXTURE** (`scripts/lib/lang-fixtures.sh` → `golden-paths/swift/vapor`): the
  build-infra probe, counted once and excluded from real-project discovery. **This package is
  discovered as an ordinary real swift project** under the same lane and runs alongside it.
- **This package has no external dependencies** (no `Package.resolved`, no network fetch), so its
  `swift test` runs offline in `swift:6.0` — a plus for CI, unlike `vapor` which fetches Vapor.
- **The Job harness skips it by construction.** `scripts/run-golden-path-jobs.sh` auto-discovers by
  **Dockerfile presence**; this client path has no Dockerfile, so it is never built/served as a Job
  (correct — a mobile client has no in-cluster image).

## Scaffold a REAL iOS app FROM this

Rewrite the one `serviceName` token in `Sources/Greeting/Greeting.swift`, drop `SelfCheckTests`, and
generate the `.xcodeproj` on a Mac (the parked half). Keep the split: put presentation logic in the
Foundation-only module so it stays Linux-CI-testable; keep SwiftUI/UIKit behind
`#if canImport(SwiftUI)`.

## `/hello` payload (the known mobile greeting)

The mobile analogue of the server contract's `/hello` body — `GreetingViewModel.payloadJSON()`:

```json
{"service":"golden-swift-ios","message":"hello, weyland"}
```

The SwiftUI screen displays the `message` (`hello, weyland`); the tests assert both the token and
the message.

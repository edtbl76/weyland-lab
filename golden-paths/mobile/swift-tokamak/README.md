# golden-path: mobile / swift-tokamak — "Swift without iOS"

A **SwiftUI-shaped** client written in Swift that compiles to **WebAssembly** and renders to the DOM,
proving the SwiftUI programming model + build chain **entirely on Linux at $0** — no macOS, no Xcode, no
iOS simulator. It is the Linux-verifiable answer to the iOS/SwiftUI surface that `swift-ios` has to park
on the Mac hardware gate.

- **Framework:** [Tokamak](https://github.com/TokamakUI/Tokamak) (a SwiftUI-compatible API) on the
  [SwiftWasm](https://swiftwasm.org) toolchain, bundled by [carton](https://github.com/swiftwasm/carton).
- **Kind:** a **client**, not a service — no HTTP contract, no Dockerfile, no k8s Job (so
  `golden-path-smoke` auto-skips it). Its smoke is a **headless web bundle** (`carton bundle`), the client
  analogue of a service path's run-to-completion Job — the same shape as `react-native` (`expo export`) and
  `flutter` (`flutter build web`).

## The contract

`GreetingView` renders the two golden-path tokens declaratively — the client analogue of the service
paths' `/hello` body `{"service":"golden-swift-tokamak","message":"hello, weyland"}`:

```swift
public struct GreetingView: View {
  public static let service = "golden-swift-tokamak"
  public static let message = "hello, weyland"
  public var body: some View { VStack { Text(GreetingView.message); Text(GreetingView.service) } }
}
```

## Layout

- `Sources/GoldenTokamakUI/` — the SwiftUI-shaped view in a **library** (so tests import it without `@main`).
- `Sources/GoldenTokamakApp/` — the thin `@main` app; `carton bundle` builds THIS product to Wasm.
- `Tests/GoldenTokamakUITests/*.tokamak.swift` — XCTest, run under `carton test --environment node`.

## Run it (all inside the pinned toolchain image)

```
docker run --rm -v "$PWD":/app -w /app ghcr.io/swiftwasm/carton:0.20.1 bash -lc 'carton test --environment node'
docker run --rm -v "$PWD":/app -w /app ghcr.io/swiftwasm/carton:0.20.1 bash -lc 'carton test --environment node -Xswiftc -DSELFCHECK'   # deliberately FAILS
docker run --rm -v "$PWD":/app -w /app ghcr.io/swiftwasm/carton:0.20.1 bash -lc 'carton bundle'   # → Bundle/ (index.html + <hash>.wasm + JS glue)
```

Or through the estate's lane driver:

```
bash scripts/run-lang-tests.sh swift-tokamak --self-check   # must detect the deliberate failure
bash scripts/run-lang-tests.sh swift-tokamak                # must pass
```

## Gotchas (hard-won)

- **The whole stack is PINNED and frozen.** Tokamak's last release is **0.11.1 (Feb 2023)** and carton's
  Docker images stop at **0.20.1** (carton 1.x moved to an SPM-plugin model with no image). So the lane
  image is `ghcr.io/swiftwasm/carton:0.20.1` (SwiftWasm Swift 5.9.1) and `Package.resolved` is **committed**.
  Frozen-but-reproducible is the right trade for a $0 lab canary; `.exact("0.11.1")` prevents drift.
- **Tests run in Node, not natively.** A native `swift test` on x86_64-Linux fails — off-wasm, Tokamak falls
  back to its **GTK** backend and needs `gtk/gtk.h`. `carton test --environment node` compiles the tests to
  Wasm and runs them in Node.js (headless, no browser), which is the real target anyway.
- **Self-check is compile-flag-gated, not env-gated.** carton test has no `--filter` (positional cases only)
  and WASI does not forward host env, so the deliberate failure is behind `#if SELFCHECK`, triggered by
  `-Xswiftc -DSELFCHECK`. Fail-closed: remove the block and the self-check stops failing → LANE BROKEN.
- **No scan lane.** swift-format shipped with Swift 6.0; the pinned SwiftWasm 5.9.1 toolchain predates it,
  so this path is **test-only** for `lang-scan`. The estate's Swift linting is already proven on the
  `swift/vapor-app` server path; adding an un-runnable scanner here would violate the fail-closed contract.
- **Discovery isolation.** `is_excluded()` keeps the swift lane off this tree, and the `*.tokamak.swift`
  test glob keeps this lane off vapor/swift-ios — verified as 0 cross-discovered projects each way.

## The iOS half is still parked

Real SwiftUI-on-iOS (simulator/device) needs macOS + Xcode, which the $0 Linux lab has no runner for — that
stays parked on the Mac hardware gate in `swift-ios`. This path covers the **programming model + build
chain**; it does not replace on-device iOS testing.

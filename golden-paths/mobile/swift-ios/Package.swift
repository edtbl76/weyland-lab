// swift-tools-version:5.10
// Golden path — Swift / iOS (SwiftUI), MOBILE ADAPTED contract (B164 workstream-1).
//
// A CLIENT app, not a server: NO HTTP endpoints, NO Dockerfile, NO k8s Job. The mobile
// variant of the golden-path contract (docs/design/golden-paths.md) is a client bundle whose
// PRESENTATION LOGIC is proven, since a $0 Linux lab has no macOS/Xcode runner for the UI build.
//
// The app is SPLIT so the maximum is Linux-verifiable:
//   Greeting  — the pure presentation LOGIC (Foundation only, NO SwiftUI/UIKit import). It
//               produces the display string `hello, weyland` + the service token `golden-swift-ios`.
//               This target + its tests BUILD AND TEST on Linux with `swift test`.
//   App       — the SwiftUI `View` + iOS `@main App` entry. Authored but PARKED behind
//               `#if canImport(SwiftUI)`, so on Linux the UI simply does not compile (the target
//               still builds — it reduces to nothing) and on macOS/Xcode it renders the Greeting.
//
// Two test targets on the one `swift test` runner:
//   AppTests       — the contract tests over the Foundation-only Greeting logic (Linux-verified).
//   SelfCheckTests — the deliberately-failing lane probe. Gated by GOLDEN_SELFCHECK=1 so a bare
//                    `swift test` SKIPS it (all green); the lane runs
//                    `GOLDEN_SELFCHECK=1 swift test --filter SelfCheckTests` and it FAILS.
import PackageDescription

let package = Package(
    name: "golden-swift-ios",
    platforms: [.macOS(.v13), .iOS(.v16)],
    targets: [
        // Pure presentation logic — Foundation only, NO SwiftUI/UIKit. Linux-verifiable.
        .target(
            name: "Greeting"
        ),
        // SwiftUI View + iOS app entry — PARKED (compiles only under Xcode/macOS via canImport guards).
        .target(
            name: "App",
            dependencies: [
                .target(name: "Greeting"),
            ]
        ),
        // Contract tests over the Foundation-only Greeting logic — runs on Linux.
        .testTarget(
            name: "AppTests",
            dependencies: [
                .target(name: "Greeting"),
            ]
        ),
        // Env-gated deliberate failure — proves the lane propagates a non-zero exit.
        .testTarget(
            name: "SelfCheckTests",
            dependencies: [
                .target(name: "Greeting"),
            ]
        ),
    ]
)

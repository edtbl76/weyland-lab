// swift-tools-version:5.7
import PackageDescription

// B164 mobile workstream — "Swift without iOS." Tokamak is a SwiftUI-COMPATIBLE API that compiles
// via the SwiftWasm toolchain to WebAssembly and renders to the DOM, so the SwiftUI programming model
// is exercised + bundled entirely on Linux at $0 (no macOS/Xcode/iOS-simulator gate — that half stays
// parked on swift-ios). The whole stack is PINNED: Tokamak's last release is 0.11.1 (Feb 2023) and
// carton's Docker images stop at 0.20.1, so the lane image is swiftwasm/carton:0.20.1 (SwiftWasm Swift
// 5.9.1) and Package.resolved is committed. Frozen-but-reproducible is the right trade for a lab canary.
let package = Package(
  name: "GoldenTokamak",
  platforms: [.macOS(.v11)],
  products: [
    .executable(name: "GoldenTokamakApp", targets: ["GoldenTokamakApp"]),
  ],
  dependencies: [
    // exact: — Tokamak is dormant; 0.11.1 is the last release and the only one this stack builds against.
    .package(url: "https://github.com/TokamakUI/Tokamak", exact: "0.11.1"),
  ],
  targets: [
    // The SwiftUI-shaped view tree lives in a LIBRARY so the tests can import it without the @main app.
    .target(name: "GoldenTokamakUI", dependencies: [
      .product(name: "TokamakShim", package: "Tokamak"),
    ]),
    // Thin @main entry; `carton bundle` builds THIS product to the Wasm web bundle.
    .executableTarget(name: "GoldenTokamakApp", dependencies: ["GoldenTokamakUI"]),
    // Tests run under `carton test --environment node` (wasm XCTest in Node.js — headless, no browser).
    .testTarget(name: "GoldenTokamakUITests", dependencies: ["GoldenTokamakUI"]),
  ]
)

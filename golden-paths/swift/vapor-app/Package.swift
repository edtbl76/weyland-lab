// swift-tools-version:5.10
// Golden path — Swift / Vapor (server-side Swift, swift.org Linux toolchain — NOT iOS).
//
// WHY THE DIRECTORY IS `vapor-app`, NOT `vapor`: SwiftPM 6.0 derives a filesystem package's identity
// from its DIRECTORY basename. A directory named `vapor` collides with the `vapor` dependency's
// identity, and SwiftPM then reports the package as depending on itself — "cyclic dependency
// golden-swift-vapor -> golden-swift-vapor requires tools-version 6.0 or later" (at tools < 6.0) or
// "product 'XCTVapor' ... not found in package 'vapor'" (at 6.0, because it searches THIS package for
// XCTVapor). Proven by isolation: the identical package builds cleanly from any dir NOT named `vapor`.
// There is no manifest-level identity override, so the fix is the directory name. Do NOT rename it back.
//
// Runnable, ephemeral, extendable. Conforms to the golden-path contract
// (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Scaffold FROM it:
//   scripts/new-service.sh swift/vapor-app <your-service>
//
// Two test targets on the one `swift test` runner:
//   AppTests       — the 4 contract tests (XCTVapor over /health /ready /metrics /hello).
//   SelfCheckTests — the deliberately-failing lane probe. Gated by GOLDEN_SELFCHECK=1 so a
//                    bare `swift test` SKIPS it (all green); the lane runs it with
//                    `GOLDEN_SELFCHECK=1 swift test --filter SelfCheckTests` and it FAILS.
import PackageDescription

let package = Package(
    name: "golden-swift-vapor-app",
    platforms: [.macOS(.v13)],
    dependencies: [
        .package(url: "https://github.com/vapor/vapor.git", from: "4.100.0"),
    ],
    targets: [
        .target(
            name: "App",
            dependencies: [
                .product(name: "Vapor", package: "vapor"),
            ]
        ),
        .executableTarget(
            name: "Run",
            dependencies: [
                .target(name: "App"),
            ]
        ),
        .testTarget(
            name: "AppTests",
            dependencies: [
                .target(name: "App"),
                .product(name: "XCTVapor", package: "vapor"),
            ]
        ),
        .testTarget(
            name: "SelfCheckTests",
            dependencies: [
                .target(name: "App"),
            ]
        ),
    ]
)

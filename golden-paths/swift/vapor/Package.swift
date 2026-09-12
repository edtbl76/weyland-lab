// swift-tools-version:5.10
// Golden path — Swift / Vapor (server-side Swift, swift.org Linux toolchain — NOT iOS).
//
// Runnable, ephemeral, extendable. Conforms to the golden-path contract
// (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Scaffold FROM it:
//   scripts/new-service.sh swift/vapor <your-service>
//
// Two test targets on the one `swift test` runner:
//   AppTests       — the 4 contract tests (XCTVapor over /health /ready /metrics /hello).
//   SelfCheckTests — the deliberately-failing lane probe. Gated by GOLDEN_SELFCHECK=1 so a
//                    bare `swift test` SKIPS it (all green); the lane runs it with
//                    `GOLDEN_SELFCHECK=1 swift test --filter SelfCheckTests` and it FAILS.
import PackageDescription

let package = Package(
    name: "golden-swift-vapor",
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

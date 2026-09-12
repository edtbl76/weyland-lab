// PARKED — the iOS app entry point. Compiles ONLY under Xcode/macOS.
//
// Behind `#if canImport(SwiftUI)`, so on Linux it reduces to nothing (the `App` target still
// builds) and on macOS/Xcode it is the `@main` SwiftUI App scene that hosts `ContentView`. This
// file, `ContentView.swift`, and an `.xcodeproj`/simulator run are the HARDWARE-GATED part of this
// golden path — see README.md § "Parked for the iOS hardware gate".
#if canImport(SwiftUI)
import SwiftUI

@main
struct GoldenSwiftIOSApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
#endif

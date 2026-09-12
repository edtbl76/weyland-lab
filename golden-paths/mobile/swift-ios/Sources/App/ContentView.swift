// PARKED — the SwiftUI presentation layer. Compiles ONLY under Xcode/macOS.
//
// The whole file is behind `#if canImport(SwiftUI)`, so on Linux it reduces to nothing and the
// `App` target still builds cleanly (this repo's CI is $0 Linux/Docker — no macOS/Xcode runner).
// On macOS/Xcode it renders `GreetingViewModel.displayText` (= "hello, weyland"). The pure logic
// it binds to lives in the Foundation-only `Greeting` module, which IS Linux-verified.
#if canImport(SwiftUI)
import SwiftUI
import Greeting

/// The demo screen: shows the known greeting produced by the platform-agnostic view-model.
public struct ContentView: View {
    private let model = GreetingViewModel()

    public init() {}

    public var body: some View {
        VStack(spacing: 12) {
            Text(model.displayText)
                .font(.title)
                .accessibilityIdentifier("greeting-message")
            Text(model.service)
                .font(.caption)
                .foregroundStyle(.secondary)
                .accessibilityIdentifier("greeting-service")
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
#endif

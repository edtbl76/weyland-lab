// Pure presentation logic for the Swift/iOS golden path — Foundation ONLY.
//
// NO `import SwiftUI`, NO `import UIKit`. Everything a SwiftUI `View` needs to render the demo
// screen lives here as plain values, so it BUILDS AND TESTS on Linux (`swift test`) even though
// the UI itself is hardware-gated to macOS/Xcode. The SwiftUI layer (Sources/App) is a thin skin
// over this: it reads `GreetingViewModel.displayText` and shows it.
import Foundation

/// The service identity carried in the greeting payload — the one token the scaffolder rewrites.
public let serviceName = "golden-swift-ios"

/// The known demo greeting: the value the UI displays and the contract asserts.
public struct Greeting: Equatable, Codable {
    public let service: String
    public let message: String

    public init(service: String = serviceName, message: String = "hello, weyland") {
        self.service = service
        self.message = message
    }
}

/// The presentation view-model the SwiftUI `ContentView` binds to. Platform-agnostic: it holds no
/// SwiftUI/UIKit type, so it is fully unit-testable on Linux.
public struct GreetingViewModel: Equatable {
    public let greeting: Greeting

    public init(greeting: Greeting = Greeting()) {
        self.greeting = greeting
    }

    /// The text the SwiftUI screen renders.
    public var displayText: String {
        greeting.message
    }

    /// The service token, exposed for the UI title / accessibility identifier.
    public var service: String {
        greeting.service
    }

    /// The known payload as canonical JSON — the mobile analogue of the server contract's
    /// `/hello` body: `{"service":"golden-swift-ios","message":"hello, weyland"}`.
    public func payloadJSON() -> String {
        // Hand-built so field order is stable and assertable regardless of encoder behaviour.
        "{\"service\":\"\(greeting.service)\",\"message\":\"\(greeting.message)\"}"
    }
}

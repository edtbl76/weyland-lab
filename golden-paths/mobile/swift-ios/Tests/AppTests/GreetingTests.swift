// Golden-path self-test (Swift/iOS) — the lane probe + contract proof over the Foundation-only
// Greeting logic. This is the MAXIMUM a $0 Linux lab can verify without macOS/Xcode: the pure
// presentation logic that the parked SwiftUI layer binds to. Runs on Linux via `swift test`.
import XCTest
@testable import Greeting

final class GreetingTests: XCTestCase {
    func testServiceToken() throws {
        XCTAssertEqual(serviceName, "golden-swift-ios")
    }

    func testDefaultGreetingMessage() throws {
        XCTAssertEqual(Greeting().message, "hello, weyland")
        XCTAssertEqual(Greeting().service, "golden-swift-ios")
    }

    func testViewModelDisplayText() throws {
        let model = GreetingViewModel()
        XCTAssertEqual(model.displayText, "hello, weyland")
        XCTAssertEqual(model.service, "golden-swift-ios")
    }

    func testViewModelPayloadJSON() throws {
        let json = GreetingViewModel().payloadJSON()
        XCTAssertEqual(json, "{\"service\":\"golden-swift-ios\",\"message\":\"hello, weyland\"}")
    }

    func testGreetingRoundTripsThroughCodable() throws {
        let original = Greeting()
        let data = try JSONEncoder().encode(original)
        let decoded = try JSONDecoder().decode(Greeting.self, from: data)
        XCTAssertEqual(decoded, original)
    }
}

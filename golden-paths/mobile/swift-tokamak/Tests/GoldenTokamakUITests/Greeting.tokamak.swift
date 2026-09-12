import XCTest
@testable import GoldenTokamakUI

// File name carries the `.tokamak.swift` infix on purpose: it is the DISCOVERY KEY for the
// swift-tokamak lane (test_glob_for → `*.tokamak.swift`), distinct from the swift lane's `*Tests.swift`
// so vapor/swift-ios are never pulled into `carton test` and this path is never pulled into `swift test`.
final class GreetingTests: XCTestCase {
  func testContractTokens() {
    XCTAssertEqual(GreetingView.service, "golden-swift-tokamak")
    XCTAssertEqual(GreetingView.message, "hello, weyland")
  }
}

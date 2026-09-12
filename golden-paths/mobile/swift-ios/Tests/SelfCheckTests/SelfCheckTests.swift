// Deliberately-failing selfcheck (Swift/iOS) — proves the swift lane PROPAGATES failure.
//
// A bare `swift test` runs this target too, so the failure is GATED behind GOLDEN_SELFCHECK=1 and
// skipped otherwise (bare run → all green). The lane surfaces it with:
//   GOLDEN_SELFCHECK=1 swift test --filter SelfCheckTests   → exits non-zero.
import XCTest

final class SelfCheckTests: XCTestCase {
    func testDeliberateFailure() throws {
        try XCTSkipUnless(
            ProcessInfo.processInfo.environment["GOLDEN_SELFCHECK"] == "1",
            "selfcheck runs only under the selfcheck lane (GOLDEN_SELFCHECK=1)"
        )
        XCTFail("selfcheck: the golden-path swift-ios lane must surface this failure (exit non-zero)")
    }
}

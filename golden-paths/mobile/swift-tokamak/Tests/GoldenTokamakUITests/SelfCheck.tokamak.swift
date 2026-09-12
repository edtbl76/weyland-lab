import XCTest
@testable import GoldenTokamakUI

/// Deliberately-failing companion. It fails ONLY when the lane compiles the tests with
/// `-Xswiftc -DSELFCHECK` (the --self-check mode); a normal `carton test` compiles the guarded body
/// away, so it passes. FLAG-GATED → FAIL-CLOSED on a rename: delete the `#if SELFCHECK` block and the
/// self-check run stops failing, which run-lang-tests.sh reports as LANE BROKEN ("a lane that cannot
/// fail is not a lane"). carton test has no --filter (positional cases only) and WASI does not forward
/// host env, so the compile flag — not an env var — is the gate here (cf. the haskell/ada flag gates).
final class SelfCheckTests: XCTestCase {
  func testDeliberateFailure() {
    #if SELFCHECK
    XCTFail("deliberate golden-path selfcheck failure — proves the runner propagates a real failure")
    #endif
  }
}

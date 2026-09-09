#include <doctest/doctest.h>

// Deliberately-failing test — proves the cpp lane PROPAGATES failure. It lives in the "selfcheck" test
// suite; a normal run uses --test-suite-exclude=selfcheck and the lane self-check uses
// --test-suite=selfcheck (only it). Suite-based (not a name filter) → fail-closed on a rename: a removed
// tag makes --test-suite=selfcheck match zero cases → doctest exits 0 → the guard reports LANE BROKEN.
TEST_SUITE("selfcheck") {
  TEST_CASE("deliberate failure") {
    FAIL("selfcheck: the golden-path cpp lane must surface this failure (exit non-zero)");
  }
}

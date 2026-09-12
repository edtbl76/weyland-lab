# Deliberately-failing test gated behind GOLDEN_SELFCHECK=1 — proves the R/plumber lane
# PROPAGATES failure. A normal `Rscript -e 'testthat::test_dir("tests")'` leaves the guard
# unset, so this file registers ZERO tests and the run stays green (exit 0). The lane
# self-check runs `GOLDEN_SELFCHECK=1 Rscript -e 'testthat::test_dir("tests")'`, which arms the
# failing test so it actually executes and exits non-zero.
#
# Fail-closed: the guard asserts the failure REASON (a message match), not merely a non-zero
# exit — a bare "did it exit non-zero?" check would pass on a MISSING test (no-match) just as it
# would on a real failure. This gating (a registered, arming test that fails with a named
# reason) makes the two distinguishable, per the estate's "absent result is never success" rule.
library(testthat)

if (identical(Sys.getenv("GOLDEN_SELFCHECK"), "1")) {
  test_that("selfcheck: the golden-path R/plumber lane must surface this failure", {
    fail("selfcheck: the golden-path R/plumber lane must surface this failure (exit non-zero)")
  })
}

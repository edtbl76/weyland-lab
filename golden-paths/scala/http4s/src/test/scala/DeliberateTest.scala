// Deliberately-failing test — proves the scala lane PROPAGATES failure. It lives in a *Deliberate*
// class; a normal `sbt test` excludes it (build.sbt Tests.Filter) and the lane self-check
// (`sbt -Dselfcheck=true test`) runs ONLY it. Fail-closed: dropping the "Deliberate" marker makes it
// run in the NORMAL lane, which is loud, not silent.
package golden

import munit.FunSuite

class DeliberateTest extends FunSuite:
  test("deliberate failure") {
    fail("selfcheck: the golden-path scala lane must surface this failure (exit non-zero)")
  }

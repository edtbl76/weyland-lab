package lab.weyland.golden.selfcheck;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/**
 * Deliberately-failing test — proves the java lane PROPAGATES failure (B88 --self-check runs the
 * `selfcheck` profile, which includes ONLY this). Fails on a real assertion, not a bare fail.
 */
class SelfCheckTest {
    @Test
    void theLaneReportsFailure() {
        assertEquals("hello, weyland", "this fixture is meant to fail",
                "selfcheck: the golden-path java lane must surface this failure (exit non-zero)");
    }
}

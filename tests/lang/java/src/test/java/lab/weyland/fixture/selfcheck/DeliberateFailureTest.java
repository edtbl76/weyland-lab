package lab.weyland.fixture.selfcheck;

import org.junit.jupiter.api.Test;

/**
 * Run ONLY by {@code run-lang-tests.sh java --self-check} (Maven profile {@code selfcheck}).
 *
 * <p>MUST fail. A lane never seen failing is not a lane — the same argument the B148 guard makes
 * about itself. Surefire excludes this package by default, so a normal {@code mvn test} cannot
 * collect it.
 */
class DeliberateFailureTest {
    @Test
    void deliberateFailure() {
        throw new AssertionError("deliberate: this failure is the point");
    }
}

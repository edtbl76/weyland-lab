package lab.weyland.flink;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.Test;

/**
 * Tests for {@link HealthStateRisk}'s row-level decisions (B88).
 *
 * <p>Before B88 this module had no test framework and no Surefire plugin, so {@code mvn test} ran
 * zero tests and exited 0. These cover the SKIP decisions that determine whether a BRFSS row feeds
 * the running mean — the place where a wrong answer is silent rather than loud.
 */
class HealthStateRiskTest {

    @Test
    void parsesANumericValue() {
        assertEquals(12.5, HealthStateRisk.parseDataValue("12.5"));
    }

    @Test
    void parsesAnIntegerValue() {
        assertEquals(7.0, HealthStateRisk.parseDataValue("7"));
    }

    @Test
    void skipsNull() {
        assertNull(HealthStateRisk.parseDataValue(null));
    }

    /**
     * BRFSS suppressed/footnote rows carry non-numeric markers. These MUST skip, not parse as 0 —
     * parsing as 0 would drag every state's mean toward zero while still emitting healthy-looking
     * output, which is exactly the kind of silent wrongness this suite exists to prevent.
     */
    @Test
    void skipsNonNumericSuppressionMarkers() {
        assertNull(HealthStateRisk.parseDataValue("*"));
        assertNull(HealthStateRisk.parseDataValue("~"));
        assertNull(HealthStateRisk.parseDataValue(""));
        assertNull(HealthStateRisk.parseDataValue("N/A"));
    }

    @Test
    void rendersNullFieldsAsThePlaceholder() {
        assertEquals("??", HealthStateRisk.str(null));
        assertEquals("Kansas", HealthStateRisk.str("Kansas"));
    }
}

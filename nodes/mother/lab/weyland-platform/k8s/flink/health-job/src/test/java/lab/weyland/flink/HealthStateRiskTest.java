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

    // ── meanStep — the running-mean arithmetic (B88, extracted from flatMap) ──────────────────────
    // The code most likely to be silently wrong: an off-by-one or a stale sum skews every state's
    // mean_risk while the job still emits healthy JSON. Nulls = first record for a key.

    @Test
    void meanStepFirstRecordIsTheValueItself() {
        double[] r = HealthStateRisk.meanStep(null, null, 42.0);
        assertEquals(1, (long) r[0]);           // count
        assertEquals(42.0, r[1], 1e-9);         // mean of a single value is the value
    }

    @Test
    void meanStepAveragesAcrossRecords() {
        // first 10, then 20 -> count 2, mean 15
        double[] first = HealthStateRisk.meanStep(null, null, 10.0);
        double[] second = HealthStateRisk.meanStep((long) first[0], first[0] * first[1], 20.0);
        assertEquals(2, (long) second[0]);
        assertEquals(15.0, second[1], 1e-9);
    }

    @Test
    void meanStepConvergesOverManyRecords() {
        // 1..100 -> mean 50.5, count 100. A drifting count or stale sum fails this.
        long count = 0; double sum = 0;
        double[] r = null;
        for (int v = 1; v <= 100; v++) {
            r = HealthStateRisk.meanStep(count == 0 ? null : count, count == 0 ? null : sum, v);
            count = (long) r[0];
            sum = r[1] * count;
        }
        assertEquals(100, (long) r[0]);
        assertEquals(50.5, r[1], 1e-9);
    }

    @Test
    void meanStepHandlesNegativeAndZero() {
        double[] r = HealthStateRisk.meanStep(1L, 10.0, -10.0);
        assertEquals(2, (long) r[0]);
        assertEquals(0.0, r[1], 1e-9);          // (10 + -10) / 2
    }

    // ── riskJson — the exact sink shape ──────────────────────────────────────────────────────────

    @Test
    void riskJsonPinsTheExactOutputShape() {
        String j = HealthStateRisk.riskJson("Kansas", 3, 12.3456);
        assertEquals("{\"state\":\"Kansas\",\"n\":3,\"mean_risk\":12.3456}", j);
    }

    @Test
    void riskJsonRoundsMeanToFourPlaces() {
        String j = HealthStateRisk.riskJson("Ohio", 1, 1.0 / 3.0);
        assertEquals("{\"state\":\"Ohio\",\"n\":1,\"mean_risk\":0.3333}", j);
    }

    @Test
    void riskJsonRendersNullStateAsPlaceholder() {
        String j = HealthStateRisk.riskJson(null, 1, 5.0);
        // str(null) -> "??"; a null Locationdesc must not produce a broken/empty state field
        assertEquals("{\"state\":\"??\",\"n\":1,\"mean_risk\":5.0000}", j);
    }
}

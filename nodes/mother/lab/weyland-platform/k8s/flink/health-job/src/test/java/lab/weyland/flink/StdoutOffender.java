package lab.weyland.flink;

/**
 * Planted-violation fixture for {@link ArchitectureTest} — deliberately writes to System.out so the
 * NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS rule is PROVEN to trip. Never referenced by production code, and
 * ImportOption.DO_NOT_INCLUDE_TESTS keeps it out of the real production check.
 */
final class StdoutOffender {

    private StdoutOffender() {
    }

    static void leak() {
        System.out.println("deliberate standard-stream access — the arch rule must catch this");
    }
}

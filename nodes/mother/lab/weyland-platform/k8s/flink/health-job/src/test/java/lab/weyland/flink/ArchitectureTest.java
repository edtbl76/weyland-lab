package lab.weyland.flink;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.EvaluationResult;
import org.junit.jupiter.api.Test;

/**
 * B152 architecture-test category — ArchUnit rules for the Flink module, run as ordinary JUnit tests in the
 * existing test-java lane. ArchUnit reads bytecode statically, so no Flink cluster / MiniCluster is needed.
 *
 * The load-bearing rule: NO access to System.out/err/printStackTrace. A streaming job must log through slf4j
 * (Flink's logging), never raw stdout — a debug println in a keyed operator floods TaskManager stdout,
 * unstructured and level-uncontrolled, and can silently cost throughput. A structural rule pins the package.
 *
 * Mirrors the dagster import-linter lane's shape: the production classes obey the rules (Green), and a planted
 * offender is PROVEN to trip the rule (asserting the violation REASON — the offending class by name — never a
 * bare boolean; the same fail-closed discipline the rest of the estate uses).
 */
class ArchitectureTest {

    // Production classes only — DO_NOT_INCLUDE_TESTS drops target/test-classes, so the planted StdoutOffender
    // below (a test class) is excluded from the real check.
    private static final JavaClasses PRODUCTION =
            new ClassFileImporter()
                    .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                    .importPackages("lab.weyland.flink");

    @Test
    void productionCodeDoesNotAccessStandardStreams() {
        NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS.check(PRODUCTION);
    }

    @Test
    void productionClassesResideInTheModulePackage() {
        classes().should().resideInAPackage("lab.weyland.flink..").check(PRODUCTION);
    }

    @Test
    void ruleCatchesAPlantedStandardStreamAccess() {
        // The permanent fail-closed proof: a fixture class that writes to System.out MUST trip the rule.
        // Assert the violation REASON (the offending class is named), never just hasViolation.
        JavaClasses offender = new ClassFileImporter().importClasses(StdoutOffender.class);
        EvaluationResult result = NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS.evaluate(offender);
        assertTrue(result.hasViolation(),
                "NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS must flag a class that writes to System.out");
        String report = result.getFailureReport().toString();
        assertTrue(report.contains("StdoutOffender"),
                "the violation must name the offending class: " + report);
    }
}

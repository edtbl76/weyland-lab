package lab.weyland.flink;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/**
 * Tests for {@link SqlRunner}'s comment stripping (B88).
 *
 * <p>Before B88 this module had no test framework and no Surefire plugin, so {@code mvn test} ran
 * zero tests and exited 0 — a green report backed by nothing.
 */
class SqlRunnerTest {

    @Test
    void stripsAFullLineComment() {
        assertEquals("\n", SqlRunner.stripLineComments("-- just a comment"));
    }

    @Test
    void stripsATrailingCommentButKeepsTheStatement() {
        assertEquals("SELECT 1 \n", SqlRunner.stripLineComments("SELECT 1 -- pick one"));
    }

    @Test
    void keepsALineWithNoComment() {
        assertEquals("SELECT 1\n", SqlRunner.stripLineComments("SELECT 1"));
    }

    @Test
    void handlesMultipleLinesIndependently() {
        // Three input lines -> three output lines: "SELECT 1 ", "SELECT 2", "" (the whole-line
        // comment collapses to empty). Each gets exactly one trailing newline.
        String out = SqlRunner.stripLineComments("SELECT 1 -- a\nSELECT 2\n-- b");
        assertEquals("SELECT 1 \nSELECT 2\n\n", out);
    }

    /**
     * DOCUMENTS A KNOWN LIMITATION rather than asserting desired behaviour: the stripper is not
     * string-literal aware, so a {@code --} inside quotes is treated as a comment. If this test
     * ever fails, someone has FIXED that — update the test and say so, do not "repair" it back.
     */
    @Test
    void isNotStringLiteralAware_knownLimitation() {
        String out = SqlRunner.stripLineComments("SELECT '--not-a-comment'");
        assertEquals("SELECT '\n", out);
        assertTrue(out.length() < "SELECT '--not-a-comment'".length(),
                "the literal is truncated; this is the documented limitation");
    }
}

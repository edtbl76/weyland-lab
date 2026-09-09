// Deliberately-failing test — proves the kotlin lane PROPAGATES failure. It carries the JUnit
// `selfcheck` tag, so a normal `gradle test` excludes it (build.gradle.kts) and the lane self-check
// (`gradle test -Pselfcheck`) runs ONLY it. Tag-based (not a test-NAME filter): dropping the tag makes
// it run in the NORMAL lane, which is loud, not silent.
package golden

import org.junit.jupiter.api.Tag
import org.junit.jupiter.api.Test
import kotlin.test.fail

class DeliberateTest {
    @Test
    @Tag("selfcheck")
    fun deliberate_failure() {
        fail("selfcheck: the golden-path kotlin lane must surface this failure (exit non-zero)")
    }
}

package lab.weyland.fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/** Proves the Java lane runs: JDK 17, Maven, Surefire and JUnit 5 are all wired. */
class HelloTest {
    @Test
    void greetingIsTheFixtureGreeting() {
        assertEquals("hello, weyland", Hello.greeting());
    }
}

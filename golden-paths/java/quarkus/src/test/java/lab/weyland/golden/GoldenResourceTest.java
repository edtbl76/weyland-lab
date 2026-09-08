package lab.weyland.golden;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.is;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

/** Golden-path self-test (Java/Quarkus) — the lane probe + contract proof, over RestAssured. */
@QuarkusTest
class GoldenResourceTest {
    @Test
    void health() { given().get("/health").then().statusCode(200).body("status", is("ok")); }

    @Test
    void ready() { given().get("/ready").then().statusCode(200).body("status", is("ready")); }

    @Test
    void hello() {
        given().get("/hello").then().statusCode(200)
                .body("message", is("hello, weyland")).body("service", is("golden-java-quarkus"));
    }

    @Test
    void metrics() {
        given().get("/hello");
        given().get("/metrics").then().statusCode(200).body(containsString("golden_hello_requests_total"));
    }
}

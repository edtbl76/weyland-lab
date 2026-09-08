package lab.weyland.golden;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.micronaut.http.HttpRequest;
import io.micronaut.http.client.HttpClient;
import io.micronaut.http.client.annotation.Client;
import io.micronaut.test.extensions.junit5.annotation.MicronautTest;
import jakarta.inject.Inject;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** Golden-path self-test (Java/Micronaut) — the lane probe + contract proof, over the Micronaut HttpClient. */
@MicronautTest
class GoldenControllerTest {

    @Inject
    @Client("/")
    HttpClient client;

    @Test
    void health() {
        Map<?, ?> r = client.toBlocking().retrieve(HttpRequest.GET("/health"), Map.class);
        assertEquals("ok", r.get("status"));
    }

    @Test
    void ready() {
        Map<?, ?> r = client.toBlocking().retrieve(HttpRequest.GET("/ready"), Map.class);
        assertEquals("ready", r.get("status"));
    }

    @Test
    void hello() {
        Map<?, ?> r = client.toBlocking().retrieve(HttpRequest.GET("/hello"), Map.class);
        assertEquals("hello, weyland", r.get("message"));
        assertEquals("golden-java-micronaut", r.get("service"));
    }

    @Test
    void metrics() {
        client.toBlocking().retrieve("/hello");
        String m = client.toBlocking().retrieve("/metrics");
        assertTrue(m.contains("golden_hello_requests_total"));
    }
}

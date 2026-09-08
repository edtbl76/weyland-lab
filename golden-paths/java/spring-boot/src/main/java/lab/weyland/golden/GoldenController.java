package lab.weyland.golden;

import io.micrometer.core.instrument.Counter;
import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import java.util.Map;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** The golden-path contract endpoints. */
@RestController
public class GoldenController {
    static final String SERVICE_NAME = "golden-java-spring-boot";

    private final PrometheusMeterRegistry registry;
    private final Counter helloHits;

    GoldenController(PrometheusMeterRegistry registry) {
        this.registry = registry;
        this.helloHits = Counter.builder("golden_hello_requests_total")
                .description("Calls to the demo /hello endpoint").register(registry);
    }

    @GetMapping("/health")
    Map<String, String> health() {
        return Map.of("status", "ok");
    }

    @GetMapping("/ready")
    Map<String, String> ready() {
        return Map.of("status", "ready");
    }

    @GetMapping(value = "/metrics", produces = MediaType.TEXT_PLAIN_VALUE)
    String metrics() {
        return registry.scrape();
    }

    @GetMapping("/hello")
    Map<String, String> hello() {
        helloHits.increment();
        return Map.of("service", SERVICE_NAME, "message", "hello, weyland");
    }
}

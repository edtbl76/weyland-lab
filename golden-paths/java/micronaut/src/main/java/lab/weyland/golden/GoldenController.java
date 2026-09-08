package lab.weyland.golden;

import io.micrometer.core.instrument.Counter;
import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import io.micronaut.http.MediaType;
import io.micronaut.http.annotation.Controller;
import io.micronaut.http.annotation.Get;
import io.micronaut.http.annotation.Produces;
import java.util.Map;

/** The golden-path contract endpoints. */
@Controller("/")
public class GoldenController {
    static final String SERVICE_NAME = "golden-java-micronaut";

    private final PrometheusMeterRegistry registry;
    private final Counter helloHits;

    GoldenController(PrometheusMeterRegistry registry) {
        this.registry = registry;
        this.helloHits = Counter.builder("golden_hello_requests_total")
                .description("Calls to the demo /hello endpoint").register(registry);
    }

    @Get("/health")
    Map<String, String> health() {
        return Map.of("status", "ok");
    }

    @Get("/ready")
    Map<String, String> ready() {
        return Map.of("status", "ready");
    }

    @Get("/metrics")
    @Produces(MediaType.TEXT_PLAIN)
    String metrics() {
        return registry.scrape();
    }

    @Get("/hello")
    Map<String, String> hello() {
        helloHits.increment();
        return Map.of("service", SERVICE_NAME, "message", "hello, weyland");
    }
}

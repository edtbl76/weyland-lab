package lab.weyland.golden;

import io.micrometer.core.instrument.MeterRegistry;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import java.util.Map;

/** Golden path Java / Quarkus (B153) — the contract endpoints. /metrics is served by micrometer
 *  (application.properties moves it to /metrics). Scaffold FROM it: scripts/new-service.sh java/quarkus &lt;name&gt;. */
@Path("/")
public class GoldenResource {
    static final String SERVICE_NAME = "golden-java-quarkus";

    @Inject
    MeterRegistry registry;

    @GET
    @Path("health")
    @Produces(MediaType.APPLICATION_JSON)
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }

    @GET
    @Path("ready")
    @Produces(MediaType.APPLICATION_JSON)
    public Map<String, String> ready() {
        return Map.of("status", "ready");
    }

    @GET
    @Path("hello")
    @Produces(MediaType.APPLICATION_JSON)
    public Map<String, String> hello() {
        registry.counter("golden_hello_requests_total").increment();
        return Map.of("service", SERVICE_NAME, "message", "hello, weyland");
    }
}

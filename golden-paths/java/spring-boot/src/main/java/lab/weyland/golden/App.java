package lab.weyland.golden;

import io.micrometer.prometheusmetrics.PrometheusConfig;
import io.micrometer.prometheusmetrics.PrometheusMeterRegistry;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

/**
 * Golden path — Java / Spring Boot (B153). Runnable, ephemeral, extendable. Conforms to the
 * golden-path contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
 * Spring Boot is the industry-standard Java option. Scaffold FROM it: scripts/new-service.sh java/spring-boot &lt;name&gt;.
 */
@SpringBootApplication
public class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }

    /** A Prometheus registry the /metrics endpoint scrapes (no actuator needed). */
    @Bean
    PrometheusMeterRegistry prometheusMeterRegistry() {
        return new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);
    }
}

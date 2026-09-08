package lab.weyland.golden;

import io.micronaut.runtime.Micronaut;

/** Golden path Java / Micronaut (B153). Scaffold FROM it: scripts/new-service.sh java/micronaut &lt;name&gt;. */
public final class Application {
    private Application() { }

    public static void main(String[] args) {
        Micronaut.run(Application.class, args);
    }
}

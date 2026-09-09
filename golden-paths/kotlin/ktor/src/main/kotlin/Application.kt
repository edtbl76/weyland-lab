// Golden path — Kotlin / Ktor (B160).
//
// The idiomatic Kotlin baseline. Runnable, ephemeral, extendable. Conforms to the golden-path contract
// (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Scaffold FROM it:
// scripts/new-service.sh kotlin/ktor <your-service>.
package golden

import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.application.Application
import io.ktor.server.application.install
import io.ktor.server.engine.embeddedServer
import io.ktor.server.metrics.micrometer.MicrometerMetrics
import io.ktor.server.netty.Netty
import io.ktor.server.plugins.contentnegotiation.ContentNegotiation
import io.ktor.server.response.respond
import io.ktor.server.response.respondText
import io.ktor.server.routing.get
import io.ktor.server.routing.routing
import io.micrometer.prometheus.PrometheusConfig
import io.micrometer.prometheus.PrometheusMeterRegistry

const val SERVICE_NAME = "golden-kotlin-ktor"

fun Application.module() {
    val registry = PrometheusMeterRegistry(PrometheusConfig.DEFAULT)
    val helloCounter = registry.counter("golden_hello_requests")
    install(MicrometerMetrics) { this.registry = registry }
    install(ContentNegotiation) { json() }
    routing {
        get("/health") { call.respond(mapOf("status" to "ok")) }
        get("/ready") { call.respond(mapOf("status" to "ready")) }
        get("/hello") {
            helloCounter.increment()
            call.respond(mapOf("service" to SERVICE_NAME, "message" to "hello, weyland"))
        }
        get("/metrics") { call.respondText(registry.scrape()) }
    }
}

fun main() {
    embeddedServer(Netty, port = 8080, host = "0.0.0.0", module = Application::module).start(wait = true)
}

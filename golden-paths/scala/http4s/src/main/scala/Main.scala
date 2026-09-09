// Golden path — Scala / http4s (B160).
//
// The idiomatic functional-Scala baseline (cats-effect + http4s Ember). Runnable, ephemeral, extendable.
// Conforms to the golden-path contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Scaffold FROM it: scripts/new-service.sh scala/http4s <your-service>.
package golden

import cats.effect.{IO, IOApp}
import com.comcast.ip4s.*
import io.prometheus.client.exporter.common.TextFormat
import io.prometheus.client.{CollectorRegistry, Counter}
import org.http4s.dsl.io.*
import org.http4s.ember.server.EmberServerBuilder
import org.http4s.headers.`Content-Type`
import org.http4s.{HttpApp, HttpRoutes, MediaType, Response}

object Main extends IOApp.Simple:
  val ServiceName = "golden-scala-http4s"
  private val registry = CollectorRegistry.defaultRegistry
  private val helloCounter = Counter.build("golden_hello_requests", "Calls to /hello").register(registry)

  private def json(body: String): IO[Response[IO]] =
    Ok(body).map(_.withContentType(`Content-Type`(MediaType.application.json)))

  // Exported so tests drive the routes in-process (no server) — the http4s analogue of a test client.
  val routes: HttpApp[IO] = HttpRoutes
    .of[IO] {
      case GET -> Root / "health" => json("""{"status":"ok"}""")
      case GET -> Root / "ready"  => json("""{"status":"ready"}""")
      case GET -> Root / "hello" =>
        helloCounter.inc()
        json(s"""{"service":"$ServiceName","message":"hello, weyland"}""")
      case GET -> Root / "metrics" =>
        val writer = java.io.StringWriter()
        TextFormat.write004(writer, registry.metricFamilySamples())
        Ok(writer.toString)
    }
    .orNotFound

  def run: IO[Unit] =
    EmberServerBuilder
      .default[IO]
      .withHost(host"0.0.0.0")
      .withPort(port"8080")
      .withHttpApp(routes)
      .build
      .use(_ => IO.never)

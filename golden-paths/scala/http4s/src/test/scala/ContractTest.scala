// Golden-path contract tests — drive the REAL routes in-process (no server) via http4s.
package golden

import cats.effect.IO
import munit.CatsEffectSuite
import org.http4s.implicits.*
import org.http4s.{Method, Request, Status, Uri}

class ContractTest extends CatsEffectSuite:

  private def get(path: Uri): IO[(Status, String)] =
    Main.routes.run(Request[IO](Method.GET, path)).flatMap(r => r.as[String].map(b => (r.status, b)))

  test("health is ok") {
    get(uri"/health").map { (status, body) =>
      assertEquals(status, Status.Ok)
      assert(body.contains("ok"))
    }
  }

  test("ready is ready") {
    get(uri"/ready").map { (status, body) =>
      assertEquals(status, Status.Ok)
      assert(body.contains("ready"))
    }
  }

  test("hello returns the known payload") {
    get(uri"/hello").map { (status, body) =>
      assertEquals(status, Status.Ok)
      assert(body.contains("hello, weyland"))
      assert(body.contains("golden-scala-http4s"))
    }
  }

  test("metrics exposes prometheus") {
    get(uri"/hello") *> get(uri"/metrics").map { (status, body) =>
      assertEquals(status, Status.Ok)
      assert(body.contains("golden_hello_requests"))
    }
  }

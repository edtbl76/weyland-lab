// Golden-path contract tests — drive the REAL app in-process via Ktor's testApplication.
package golden

import io.ktor.client.request.get
import io.ktor.client.statement.bodyAsText
import io.ktor.http.HttpStatusCode
import io.ktor.server.testing.testApplication
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ContractTest {
    @Test
    fun health_is_ok() = testApplication {
        application { module() }
        val res = client.get("/health")
        assertEquals(HttpStatusCode.OK, res.status)
        assertTrue(res.bodyAsText().contains("ok"))
    }

    @Test
    fun ready_is_ready() = testApplication {
        application { module() }
        val res = client.get("/ready")
        assertEquals(HttpStatusCode.OK, res.status)
        assertTrue(res.bodyAsText().contains("ready"))
    }

    @Test
    fun hello_returns_the_known_payload() = testApplication {
        application { module() }
        val res = client.get("/hello")
        assertEquals(HttpStatusCode.OK, res.status)
        val body = res.bodyAsText()
        assertTrue(body.contains("hello, weyland"))
        assertTrue(body.contains("golden-kotlin-ktor"))
    }

    @Test
    fun metrics_exposes_prometheus() = testApplication {
        application { module() }
        client.get("/hello") // touch the counter so it appears in the exposition
        val res = client.get("/metrics")
        assertEquals(HttpStatusCode.OK, res.status)
        assertTrue(res.bodyAsText().contains("golden_hello_requests"))
    }
}

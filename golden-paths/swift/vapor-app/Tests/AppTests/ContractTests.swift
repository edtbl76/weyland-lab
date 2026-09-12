// Golden-path self-test (Swift/Vapor) — the lane probe + contract proof, over XCTVapor.
@testable import App
import XCTVapor

final class ContractTests: XCTestCase {
    private func withApp(_ body: (Application) async throws -> Void) async throws {
        let app = try await Application.make(.testing)
        do {
            try await configure(app)
            try await body(app)
        } catch {
            try await app.asyncShutdown()
            throw error
        }
        try await app.asyncShutdown()
    }

    func testHealthIsOK() async throws {
        try await withApp { app in
            try await app.test(.GET, "health", afterResponse: { res async in
                XCTAssertEqual(res.status, .ok)
                XCTAssertTrue(res.body.string.contains("\"status\":\"ok\""), res.body.string)
            })
        }
    }

    func testReadyIsReady() async throws {
        try await withApp { app in
            try await app.test(.GET, "ready", afterResponse: { res async in
                XCTAssertEqual(res.status, .ok)
                XCTAssertTrue(res.body.string.contains("\"status\":\"ready\""), res.body.string)
            })
        }
    }

    func testHelloReturnsKnownPayload() async throws {
        try await withApp { app in
            try await app.test(.GET, "hello", afterResponse: { res async in
                XCTAssertEqual(res.status, .ok)
                let body = res.body.string
                XCTAssertTrue(body.contains("\"service\":\"\(serviceName)\""), body)
                XCTAssertTrue(body.contains("\"message\":\"hello, weyland\""), body)
            })
        }
    }

    func testMetricsExposesPrometheus() async throws {
        try await withApp { app in
            try await app.test(.GET, "hello", afterResponse: { _ async in })
            try await app.test(.GET, "metrics", afterResponse: { res async in
                XCTAssertEqual(res.status, .ok)
                XCTAssertTrue(res.body.string.contains("golden_hello_requests_total"), res.body.string)
            })
        }
    }
}

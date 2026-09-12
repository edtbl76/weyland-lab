import Vapor

/// The service identity carried in the `/hello` payload — one token the scaffolder rewrites.
public let serviceName = "golden-swift-vapor-app"

struct StatusResponse: Content {
    let status: String
}

struct HelloResponse: Content {
    let service: String
    let message: String
}

/// Wires the golden-path contract routes: /health /ready /metrics /hello.
public func routes(_ app: Application) throws {
    app.get("health") { _ in
        StatusResponse(status: "ok")
    }

    app.get("ready") { _ in
        StatusResponse(status: "ready")
    }

    app.get("hello") { _ in
        HelloCounter.shared.increment()
        return HelloResponse(service: serviceName, message: "hello, weyland")
    }

    app.get("metrics") { _ -> Response in
        let body = HelloCounter.shared.exposition()
        var headers = HTTPHeaders()
        headers.contentType = HTTPMediaType(type: "text", subType: "plain", parameters: ["version": "0.0.4"])
        return Response(status: .ok, headers: headers, body: .init(string: body))
    }
}

import Vapor

/// Configures the Vapor application: binds 0.0.0.0:8080 and registers the contract routes.
///
/// GOTCHA: Vapor defaults to hostname 127.0.0.1, which is unreachable from outside the
/// container. A golden path MUST bind 0.0.0.0 or the k8s Job / docker smoke can never curl it.
public func configure(_ app: Application) throws {
    app.http.server.configuration.hostname = "0.0.0.0"
    app.http.server.configuration.port = 8080
    try routes(app)
}

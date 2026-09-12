import App
import Vapor

// Golden-path entrypoint (Swift/Vapor). Boots the app, configures the contract routes,
// and serves on 0.0.0.0:8080 until terminated.
var env = try Environment.detect()
try LoggingSystem.bootstrap(from: &env)

let app = try await Application.make(env)
do {
    try await configure(app)
    try await app.execute()
    try await app.asyncShutdown()
} catch {
    app.logger.report(error: error)
    try? await app.asyncShutdown()
    throw error
}

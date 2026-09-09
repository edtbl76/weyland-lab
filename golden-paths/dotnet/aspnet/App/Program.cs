// Golden path — C#/.NET / ASP.NET Core minimal API (B160).
//
// The idiomatic .NET baseline. Runnable, ephemeral, extendable. Conforms to the golden-path contract
// (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Scaffold FROM it:
// scripts/new-service.sh dotnet/aspnet <your-service>.
//
// `public partial class Program {}` at the end makes the top-level-statement entry point referable by
// WebApplicationFactory<Program>, so the contract tests drive the real app in-process (../tests/).
using Prometheus;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

const string serviceName = "golden-dotnet-aspnet";
var helloHits = Metrics.CreateCounter("golden_hello_requests_total", "Calls to the demo /hello endpoint");

app.UseHttpMetrics();                 // per-request Prometheus metrics
app.MapGet("/health", () => Results.Json(new { status = "ok" }));
app.MapGet("/ready", () => Results.Json(new { status = "ready" }));
app.MapGet("/hello", () =>
{
    helloHits.Inc();
    return Results.Json(new { service = serviceName, message = "hello, weyland" });
});
app.MapMetrics();                     // GET /metrics (Prometheus exposition)

app.Run();                            // binds :8080 — the .NET 8 aspnet image defaults ASPNETCORE_URLS to http://+:8080

public partial class Program { }

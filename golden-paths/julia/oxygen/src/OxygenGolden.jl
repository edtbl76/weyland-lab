# Golden path — Julia / Oxygen.jl (B160-style extended wave).
#
# The idiomatic Oxygen.jl micro-framework baseline. Runnable, ephemeral, extendable. Conforms to the
# golden-path contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello on :8080.
# Scaffold FROM it: scripts/new-service.sh julia/oxygen <your-service>.
module OxygenGolden

using Oxygen
using HTTP
using JSON3

const SERVICE_NAME = "golden-julia-oxygen"

# --- pure payload builders (unit-testable without a socket) ---
health_payload() = Dict("status" => "ok")
ready_payload()  = Dict("status" => "ready")
hello_payload()  = Dict("service" => SERVICE_NAME, "message" => "hello, weyland")

# --- minimal Prometheus counter for the demo endpoint ---
const HELLO_HITS = Ref(0)

function metrics_text()
    return string(
        "# HELP golden_hello_requests_total Calls to the demo /hello endpoint\n",
        "# TYPE golden_hello_requests_total counter\n",
        "golden_hello_requests_total ", HELLO_HITS[], "\n",
    )
end

# register! wires the contract routes onto Oxygen's router. Idempotent: re-registering a path overwrites.
function register!()
    @get "/health" () -> health_payload()
    @get "/ready" () -> ready_payload()
    @get "/hello" function ()
        HELLO_HITS[] += 1
        return hello_payload()
    end
    # /metrics is Prometheus text exposition, so return an explicit Response with the text content-type
    # (a returned Dict would be JSON-serialized). Oxygen's own metrics dashboard is disabled in start().
    @get "/metrics" () -> HTTP.Response(200, ["Content-Type" => "text/plain; version=0.0.4"], metrics_text())
    return nothing
end

# start boots the HTTP server on :8080. async=true returns the server handle for tests to close.
# docs=false / metrics=false disable Oxygen's Swagger UI and its built-in /metrics dashboard so the
# contract surface is exactly the four routes above.
function start(; host::AbstractString = "0.0.0.0", port::Integer = 8080, async::Bool = false)
    register!()
    return serve(; host = host, port = port, async = async, docs = false, metrics = false)
end

end # module

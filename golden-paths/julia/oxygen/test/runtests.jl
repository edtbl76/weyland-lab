# Golden-path self-test (Julia/Oxygen) — the lane probe + contract proof.
#
# Normal run (`Pkg.test()`): starts the real server on an ephemeral port, drives the four contract
# routes over HTTP, asserts /hello's known payload. The `selfcheck` set is EXCLUDED.
#
# Selfcheck run (`GOLDEN_SELFCHECK=1 Pkg.test()`, or `Pkg.test(test_args=["selfcheck"])`): additionally
# runs a deliberately-failing test so the lane is proven to PROPAGATE failure (Pkg.test throws -> the
# process exits non-zero). Fail-closed: the selfcheck command MUST exit non-zero; a green selfcheck run
# means the failure did not surface and the lane is broken.
using Test
using OxygenGolden
using Oxygen
using HTTP
using JSON3

selfcheck = get(ENV, "GOLDEN_SELFCHECK", "") == "1" || ("selfcheck" in ARGS)

const PORT = 8123

function wait_ready(port; tries = 120)
    for _ in 1:tries
        try
            r = HTTP.get("http://127.0.0.1:$port/ready"; retry = false, connect_timeout = 1)
            r.status == 200 && return true
        catch
            sleep(0.25)
        end
    end
    return false
end

@testset "contract" begin
    server = OxygenGolden.start(; port = PORT, async = true)
    try
        @test wait_ready(PORT)

        r = HTTP.get("http://127.0.0.1:$PORT/health")
        @test r.status == 200
        @test JSON3.read(r.body).status == "ok"

        r = HTTP.get("http://127.0.0.1:$PORT/ready")
        @test r.status == 200
        @test JSON3.read(r.body).status == "ready"

        r = HTTP.get("http://127.0.0.1:$PORT/hello")
        @test r.status == 200
        body = JSON3.read(r.body)
        @test body.service == "golden-julia-oxygen"
        @test body.message == "hello, weyland"

        r = HTTP.get("http://127.0.0.1:$PORT/metrics")
        @test r.status == 200
        text = String(r.body)
        @test occursin("golden_hello_requests_total", text)
        # /hello was hit once above -> the counter must reflect it (not merely be present)
        @test occursin("golden_hello_requests_total 1", text)
    finally
        # Oxygen's global terminate stops the async server started above.
        Oxygen.terminate()
    end
end

if selfcheck
    @testset "selfcheck" begin
        # Deliberate failure — proves `Pkg.test()` surfaces a failing @test as a non-zero exit.
        @test false
    end
end

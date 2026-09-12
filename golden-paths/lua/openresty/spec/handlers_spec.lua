-- Golden-path self-test (Lua/OpenResty) — the lane probe + contract proof, over the pure payload builders.
-- busted runs headless (no nginx, no `ngx`), so we unit-test handlers.lua directly — same strategy the
-- C/C++ golden paths use. The real OpenResty server is proven by the curl smoke.
package.path = "./lua/?.lua;" .. package.path
local handlers = require("handlers")

describe("golden-lua-openresty contract payloads", function()
  it("health is ok", function()
    assert.are.equal('{"status":"ok"}', handlers.health_json())
  end)

  it("ready is ready", function()
    assert.are.equal('{"status":"ready"}', handlers.ready_json())
  end)

  it("hello returns the known payload", function()
    local body = handlers.hello_json()
    assert.is_truthy(body:find("hello, weyland", 1, true))
    assert.is_truthy(body:find("golden-lua-openresty", 1, true))
    assert.are.equal('{"service":"golden-lua-openresty","message":"hello, weyland"}', body)
  end)

  it("metrics exposes a valid prometheus exposition", function()
    local m = handlers.metrics_text()
    assert.is_truthy(m:find("golden_hello_requests_total", 1, true))
    assert.is_truthy(m:find("# HELP", 1, true))
    assert.is_truthy(m:find("# TYPE golden_hello_requests_total counter", 1, true))
  end)
end)

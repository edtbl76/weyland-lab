-- Golden path — Lua / OpenResty (B160-style extended wave).
--
-- Pure response-builders — the contract's payloads, factored out so they are unit-testable under headless
-- busted without an HTTP layer (busted cannot bind nginx; OpenResty's `ngx` API only exists inside a
-- running worker). These functions cover the payload logic; the smoke curls the real OpenResty server
-- end-to-end. JSON is hand-rolled (like the C/C++ golden paths) so the module stays dependency-free —
-- no cjson needed to unit-test the byte-exact payload.
local M = {}

M.service = "golden-lua-openresty"

function M.health_json()
  return '{"status":"ok"}'
end

function M.ready_json()
  return '{"status":"ready"}'
end

function M.hello_json()
  return '{"service":"' .. M.service .. '","message":"hello, weyland"}'
end

-- Prometheus text exposition, hand-rolled to stay dependency-free. A minimal valid exposition:
-- one HELP line, one TYPE line, one sample.
function M.metrics_text()
  return "# HELP golden_hello_requests_total Calls to /hello\n"
    .. "# TYPE golden_hello_requests_total counter\n"
    .. "golden_hello_requests_total 0\n"
end

return M

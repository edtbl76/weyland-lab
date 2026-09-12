-- luacheck config for the lua/openresty golden path — keeps the scan lane clean.
std = "max"
-- OpenResty injects `ngx` into the content_by_lua_block runtime; declare it so luacheck doesn't flag it.
globals = { "ngx" }
-- busted's spec DSL (describe/it/assert/...) — treat spec/ as the busted std.
files["spec/"] = { std = "+busted" }

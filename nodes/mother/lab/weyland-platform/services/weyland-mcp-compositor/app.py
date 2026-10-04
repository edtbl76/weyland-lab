"""weyland-mcp-compositor — B17+B19 Phase 3. A FastMCP proxy that aggregates the read-only MCP fleet + the
tool-server's read `/mcp` into ONE MCP endpoint, tools namespaced per upstream (`grafana_*`, `trino_*`, `context_*`…).
Fronted by weyland-mcp-gateway (the single auth + actor-injection point).

ACTS ARE NOT HERE. Only read surfaces are composed. The tool-server's `/mcp-act` (+ `/pipeline/trigger`, `/evals/*`)
stay on the direct gateway→tool-server path where `policy.gate` + the anti-spoof AuthorizationPolicy govern them.

create_proxy(MCPConfig) mounts each server with its config key as the tool prefix. Per-upstream transport is declared
(streamable-http vs sse). Upstreams + their read-only allowlists live in config.py (unit-tested). Each upstream URL is
env-overridable; **set its URL env to empty to SKIP it** (for bisecting a backend that won't handshake)."""
import dataclasses
import os

from fastmcp.server import create_proxy

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from config import build_servers, is_blocked, rewrite_arguments

servers = build_servers(os.environ)
print(f"[compositor] mounting upstreams: {sorted(servers)}", flush=True)


class ReadOnlyAllowlist(Middleware):
    """B182 — a read-only upstream's tools reach the fleet only if allowlisted (config.READ_ONLY): hidden from
    tools/list AND refused on call, so a client that knows a write tool's name still cannot call it. Allowed calls get
    config.rewrite_arguments (a memory search becomes semantic). The context is a frozen dataclass — replace, not set."""

    async def on_list_tools(self, context, call_next):
        return [t for t in await call_next(context) if not is_blocked(t.name, servers)]

    async def on_call_tool(self, context, call_next):
        if is_blocked(context.message.name, servers):
            raise ToolError(f"{context.message.name} is not allowed through the read-only fleet")
        args = context.message.arguments or {}
        new = rewrite_arguments(context.message.name, args, servers)
        if new is not args:
            context = dataclasses.replace(context, message=context.message.model_copy(update={"arguments": new}))
        return await call_next(context)


app = create_proxy({"mcpServers": servers}, name="weyland-mcp-compositor")
app.add_middleware(ReadOnlyAllowlist())

if __name__ == "__main__":
    app.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

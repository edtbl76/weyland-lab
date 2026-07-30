"""weyland-mcp-compositor — B17+B19 Phase 3. A FastMCP proxy that aggregates the read-only MCP fleet + the
tool-server's read `/mcp` into ONE MCP endpoint, tools namespaced per upstream (`grafana_*`, `trino_*`, `context_*`…).
Fronted by weyland-mcp-gateway (the single auth + actor-injection point).

ACTS ARE NOT HERE. Only read surfaces are composed. The tool-server's `/mcp-act` (+ `/pipeline/trigger`, `/evals/*`)
stay on the direct gateway→tool-server path where `policy.gate` + the anti-spoof AuthorizationPolicy govern them.

create_proxy(MCPConfig) mounts each server with its config key as the tool prefix. Per-upstream transport is declared
(streamable-http vs sse). Each upstream URL is env-overridable; **set its URL env to empty to SKIP it** (for bisecting a
backend that won't handshake — the aggregate `tools/list` fans out to all backends and hangs if one blocks)."""
import os

from fastmcp.server import create_proxy

# name -> (URL env var, default in-cluster URL, transport)
UPSTREAMS = {
    "context":  ("CONTEXT_URL",  "http://weyland-tool-server.weyland.svc.cluster.local:8080/mcp", "http"),
    "grafana":  ("GRAFANA_URL",  "http://grafana-mcp.weyland.svc.cluster.local:8000/mcp", "http"),
    "trino":    ("TRINO_URL",    "http://trino-mcp.weyland.svc.cluster.local:8080/mcp", "http"),
    "k8s":      ("K8S_URL",      "http://k8s-mcp.weyland.svc.cluster.local:8080/mcp", "http"),
    "postgres": ("POSTGRES_URL", "http://postgres-mcp.weyland.svc.cluster.local:8000/sse", "sse"),
    "neo4j":    ("NEO4J_URL",    "http://neo4j-mcp.weyland.svc.cluster.local:8000/mcp/", "http"),
    "datahub":  ("DATAHUB_URL",  "http://datahub-mcp.weyland.svc.cluster.local:8000/mcp", "http"),
}

servers = {}
for name, (env, default, transport) in UPSTREAMS.items():
    url = os.environ.get(env, default)
    if url:  # empty string → skip (bisecting)
        servers[name] = {"url": url, "transport": transport}
print(f"[compositor] mounting upstreams: {sorted(servers)}", flush=True)

app = create_proxy({"mcpServers": servers}, name="weyland-mcp-compositor")

if __name__ == "__main__":
    app.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

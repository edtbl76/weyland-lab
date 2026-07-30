"""weyland-mcp-compositor — B17+B19 Phase 3. A FastMCP proxy that aggregates the read-only MCP fleet + the
tool-server's read `/mcp` into ONE MCP endpoint, with tools namespaced per upstream (`grafana_*`, `trino_*`,
`context_*`, …). Fronted by weyland-mcp-gateway (the single auth + actor-injection point).

ACTS ARE NOT HERE. Only read surfaces are composed. The tool-server's `/mcp-act` (and `/pipeline/trigger`, `/evals/*`)
stay on the direct gateway→tool-server path, where `policy.gate` + the anti-spoof AuthorizationPolicy govern them.

FastMCP.as_proxy(MCPConfig) mounts each server with its config key as the tool prefix. Transport is inferred/declared
per upstream: streamable-http (`/mcp`) for most, SSE (`/sse`) for postgres-mcp (0.3.0 has no streamable-http)."""
import os

from fastmcp import FastMCP


def _u(env: str, default: str) -> str:
    return os.environ.get(env, default)


# 7 read surfaces. Keys become the tool-name prefix. In-cluster svc URLs (overridable via env).
CONFIG = {
    "mcpServers": {
        "context":  {"url": _u("CONTEXT_URL",  "http://weyland-tool-server.weyland.svc.cluster.local:8080/mcp"), "transport": "http"},
        "grafana":  {"url": _u("GRAFANA_URL",  "http://grafana-mcp.weyland.svc.cluster.local:8000/mcp"), "transport": "http"},
        "trino":    {"url": _u("TRINO_URL",    "http://trino-mcp.weyland.svc.cluster.local:8080/mcp"), "transport": "http"},
        "k8s":      {"url": _u("K8S_URL",      "http://k8s-mcp.weyland.svc.cluster.local:8080/mcp"), "transport": "http"},
        "postgres": {"url": _u("POSTGRES_URL", "http://postgres-mcp.weyland.svc.cluster.local:8000/sse"), "transport": "sse"},
        "neo4j":    {"url": _u("NEO4J_URL",    "http://neo4j-mcp.weyland.svc.cluster.local:8000/mcp/"), "transport": "http"},
        "datahub":  {"url": _u("DATAHUB_URL",  "http://datahub-mcp.weyland.svc.cluster.local:8000/mcp"), "transport": "http"},
    }
}

app = FastMCP.as_proxy(CONFIG, name="weyland-mcp-compositor")

if __name__ == "__main__":
    app.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

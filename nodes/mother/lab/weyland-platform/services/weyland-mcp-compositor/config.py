"""Upstream config for weyland-mcp-compositor — pure (no FastMCP import), so it is unit-testable.

name -> (URL env var, default in-cluster URL, transport). An EMPTY URL skips the upstream (bisecting a backend that
won't handshake; the aggregate `tools/list` fans out to all backends and hangs if one blocks).

READ-ONLY upstreams carry an ALLOWLIST, enforced by app.py's middleware through `is_blocked()`: any of their tools not
listed is hidden from tools/list and refused on call — so a write tool, or one a future version adds, never reaches
the fleet. (FastMCP 3.4.5's per-server `tools`/`include_tags` config does not do this: the tag is not applied and
include_tags hid all 21 tools — observed 2026-10-03.) The fleet is read surfaces only (app.py).
"""

UPSTREAMS = {
    "context":  ("CONTEXT_URL",  "http://weyland-tool-server.weyland.svc.cluster.local:8080/mcp", "http"),
    "grafana":  ("GRAFANA_URL",  "http://grafana-mcp.weyland.svc.cluster.local:8000/mcp", "http"),
    "trino":    ("TRINO_URL",    "http://trino-mcp.weyland.svc.cluster.local:8080/mcp", "http"),
    "k8s":      ("K8S_URL",      "http://k8s-mcp.weyland.svc.cluster.local:8080/mcp", "http"),
    "postgres": ("POSTGRES_URL", "http://postgres-mcp.weyland.svc.cluster.local:8000/sse", "sse"),
    "neo4j":    ("NEO4J_URL",    "http://neo4j-mcp.weyland.svc.cluster.local:8000/mcp/", "http"),
    "datahub":  ("DATAHUB_URL",  "http://datahub-mcp.weyland.svc.cluster.local:8000/mcp", "http"),
    # B182 (2026-10-03) — the shared agent memory: Basic Memory on rogueone. No default: its LAN address lives in the
    # manifest (k8s/mcp-servers/compositor.yaml, MEMORY_URL). rogueone's ufw admits only mother, where this pod runs.
    "memory":   ("MEMORY_URL",   "", "http"),
}

# The memory tools the fleet may expose — recall only. Basic Memory's write_note / edit_note / delete_note / move_note
# and project tools stay OUT: coding agents write through Bifrost; the operator (this fleet's client) only recalls.
MEMORY_READ_TOOLS = ("search_notes", "read_note", "view_note", "read_content", "build_context", "recent_activity",
                     "list_directory")

READ_ONLY = {"memory": MEMORY_READ_TOOLS}


def build_servers(env) -> dict:
    """The MCPConfig `mcpServers` mapping for the upstreams whose URL is set in `env` (or defaulted)."""
    servers = {}
    for name, (var, default, transport) in UPSTREAMS.items():
        url = env.get(var, default)
        if not url:
            continue
        servers[name] = {"url": url, "transport": transport}
    return servers


def is_blocked(tool_name: str, servers: dict) -> bool:
    """True when `tool_name` belongs to a mounted READ-ONLY upstream and is not on its allowlist.

    With several upstreams FastMCP prefixes each tool with its upstream name (`memory_search_notes`); with one upstream
    it does not (observed) — then every tool belongs to that one."""
    for upstream, allowed in READ_ONLY.items():
        if upstream not in servers:
            continue
        if len(servers) == 1:
            return tool_name not in allowed
        prefix = f"{upstream}_"
        if tool_name.startswith(prefix):
            return tool_name[len(prefix):] not in allowed
    return False

"""Load the composed MCP fleet's read tools into the operator (B17+B19 Phase 3 — the agent edge).

The 6 read-only subsystem servers (grafana/trino/k8s/postgres/neo4j/datahub) are aggregated by the FastMCP compositor
and exposed at the gateway's `/mcp-fleet` (Keycloak-authed → verified actor). We surface them to the ReAct agent as
LangChain tools via langchain-mcp-adapters, namespaced `grafana_*`, `trino_*`, `k8s_*`, `postgres_*`, `neo4j_*`,
`datahub_*`.

Token refresh: MultiServerMCPClient is stateless (a fresh MCP session per tool call), so a custom `httpx.Auth` mints a
FRESH operator client_credentials token on EVERY request (reusing `act._token()`, which caches + refreshes ~30s before
expiry). No stale-token failures on a long-running operator. If no token is wired (OPERATOR_CLIENT_SECRET unset) the
fleet is skipped and the operator runs with its base tools.

Curation: these are READ tools (safe — no confirm-step needed). All load by default; set `FLEET_PREFIXES=k8s,grafana`
to narrow to specific subsystems if the full set (~90 tools) degrades gpt-oss:20b's tool selection."""
import asyncio
import os

import httpx

from act import GATEWAY, _token

FLEET_URL = os.getenv("FLEET_URL", GATEWAY.rstrip("/") + "/mcp-fleet")
_ALLOW = [p.strip() for p in os.getenv("FLEET_PREFIXES", "").split(",") if p.strip()]


class _KeycloakAuth(httpx.Auth):
    """Inject a fresh operator Bearer on every request — the gateway validates it → verified actor `weyland-operator`."""

    def auth_flow(self, request):
        tok = _token()
        if tok:
            request.headers["Authorization"] = f"Bearer {tok}"
        yield request


def load_fleet_tools():
    """Return the fleet's read tools as LangChain tools (empty list on any failure — the operator must still start)."""
    if not _token():
        print("[fleet] no operator token (OPERATOR_CLIENT_SECRET unset) — fleet tools NOT loaded", flush=True)
        return []
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        client = MultiServerMCPClient(
            {"fleet": {"url": FLEET_URL, "transport": "streamable_http", "auth": _KeycloakAuth()}}
        )
        tools = asyncio.run(client.get_tools())
        if _ALLOW:
            tools = [t for t in tools if any(t.name.startswith(p + "_") for p in _ALLOW)]
            print(f"[fleet] filtered to prefixes {_ALLOW}", flush=True)
        print(f"[fleet] loaded {len(tools)} read tools from {FLEET_URL}", flush=True)
        return tools
    except Exception as exc:
        print(f"[fleet] failed to load fleet tools ({exc}) — running with base tools", flush=True)
        return []

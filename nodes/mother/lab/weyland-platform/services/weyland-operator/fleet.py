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
_ALLOW = [p.strip() for p in os.getenv("FLEET_PREFIXES", "").split(",") if p.strip()]      # subsystem filter
_ALLOW_NAMES = [n.strip() for n in os.getenv("FLEET_TOOLS", "").split(",") if n.strip()]   # exact tool-name allowlist (tightest)


class _KeycloakAuth(httpx.Auth):
    """Inject a fresh operator Bearer on every request — the gateway validates it → verified actor `weyland-operator`."""

    def auth_flow(self, request):
        tok = _token()
        if tok:
            request.headers["Authorization"] = f"Bearer {tok}"
        yield request


_SUBSYSTEM_DESC = {
    "k8s":      "the Kubernetes cluster (pods, namespaces, events, nodes, logs)",
    "trino":    "the Trino lakehouse (SQL over iceberg.* + dbt marts; catalogs / schemas / tables)",
    "grafana":  "Grafana (dashboards, Prometheus/Loki queries, alerts, datasources)",
    "neo4j":    "the Neo4j graph store (read Cypher + schema)",
    "datahub":  "the DataHub catalog (metadata search + data lineage)",
    "postgres": "the Postgres database (schemas, objects, read-only SQL, health)",
}


def _group_by_subsystem(tools):
    groups = {}
    for t in tools:
        groups.setdefault(t.name.split("_", 1)[0], []).append(t)
    return groups


def build_router_tools(flat_tools, llm):
    """Two-stage routing: return one 'subsystem' router tool per group (k8s/trino/…). Each router runs a FOCUSED
    sub-agent that sees only that subsystem's tools — so the top agent chooses among ~6 routers (not ~91 tools), and
    the sub-agent chooses among ~a dozen. Full coverage, small active tool-set at every step. Empty if no fleet."""
    if not flat_tools:
        return []
    from langchain_core.tools import StructuredTool
    from langgraph.prebuilt import create_react_agent

    routers = []
    for subsystem, tools in _group_by_subsystem(flat_tools).items():
        sub_agent = create_react_agent(llm, tools)
        desc = _SUBSYSTEM_DESC.get(subsystem, f"the {subsystem} subsystem")

        async def _route(request: str, _agent=sub_agent, _desc=desc):
            sys = (f"You query {_desc} for the weyland homelab. Pick the single best tool, run it, and answer from its "
                   f"output concisely. NEVER tell the user to run kubectl/SQL/curl themselves — YOU run it and report "
                   f"the result. If a tool errors or returns nothing, say so plainly.")
            r = await _agent.ainvoke({"messages": [("system", sys), ("user", request)]})
            return r["messages"][-1].content

        routers.append(StructuredTool.from_function(
            coroutine=_route, name=subsystem,
            description=(f"Query {desc}. Pass a natural-language request describing what you need; this selects the "
                         f"right {subsystem} tool, runs it live, and returns the result. Use for ANY {subsystem} question."),
        ))
    print(f"[fleet] built {len(routers)} subsystem routers: {sorted(_group_by_subsystem(flat_tools))}", flush=True)
    return routers


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
        # The MLflow AI Gateway strictly validates tool schemas: function.parameters MUST include a `properties` map,
        # but some MCP no-arg tools emit a bare {"type":"object"} → the Gateway 400s the whole request. Normalize.
        _fixed = 0
        for t in tools:
            sch = getattr(t, "args_schema", None)
            if isinstance(sch, dict) and sch.get("type") == "object" and "properties" not in sch:
                sch["properties"] = {}
                _fixed += 1
        print(f"[fleet] normalized {_fixed} tool schema(s) for gateway strict validation", flush=True)
        if _ALLOW:
            tools = [t for t in tools if any(t.name.startswith(p + "_") for p in _ALLOW)]
            print(f"[fleet] filtered to prefixes {_ALLOW}", flush=True)
        if _ALLOW_NAMES:
            tools = [t for t in tools if t.name in _ALLOW_NAMES]
            print(f"[fleet] filtered to {len(_ALLOW_NAMES)} named tools", flush=True)
        print(f"[fleet] loaded {len(tools)} read tools from {FLEET_URL}", flush=True)
        return tools
    except Exception as exc:
        print(f"[fleet] failed to load fleet tools ({exc}) — running with base tools", flush=True)
        return []

"""List the MCP fleet — every server and its tools — by querying the compositor's aggregated tools/list (so it reflects
what's ACTUALLY live, not a hardcoded doc). B17+B19 Phase 3.

Run from a pod that can reach the compositor + has httpx (the guard pod does):
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/list_mcp_fleet.py
"""
import collections
import json

import httpx

COMPOSITOR = "http://weyland-mcp-compositor.weyland.svc.cluster.local:8000/mcp"

# prefix -> (surface, in-cluster endpoint, read-only enforcement)
SERVERS = {
    "grafana":  ("dashboards / Prometheus / alerts",          "grafana-mcp:8000/mcp",  "--disable-write"),
    "trino":    ("lakehouse SQL (iceberg.* + dbt marts)",      "trino-mcp:8080/mcp",    "server read-only + Ranger"),
    "k8s":      ("cluster read (pods / events / nodes)",       "k8s-mcp:8080/mcp",      "--read-only + view RBAC"),
    "postgres": ("Postgres (schemas / objects / read SQL)",    "postgres-mcp:8000/sse", "restricted (READ ONLY txn)"),
    "neo4j":    ("graph / Cypher (read)",                      "neo4j-mcp:8000/mcp/",   "NEO4J_READ_ONLY"),
    "datahub":  ("catalog search + data lineage",              "datahub-mcp:8000/mcp",  "mutation tools off"),
}


def _fleet_tools():
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    c = httpx.Client(timeout=20, follow_redirects=True)
    r = c.post(COMPOSITOR, headers=h, json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "ls", "version": "0"}}})
    sid = r.headers.get("mcp-session-id")
    h2 = {**h, **({"mcp-session-id": sid} if sid else {})}
    c.post(COMPOSITOR, headers=h2, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    r2 = c.post(COMPOSITOR, headers=h2, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    d = r2.text
    lines = [x[5:].strip() for x in d.splitlines() if x.startswith("data:")]
    return json.loads(lines[-1] if lines else d)["result"]["tools"]


groups = collections.defaultdict(list)
for t in _fleet_tools():
    groups[t["name"].split("_", 1)[0]].append(t["name"])

total = sum(len(v) for v in groups.values())
print(f"MCP fleet — {total} read tools across {len(groups)} servers (via the compositor at /mcp-fleet)\n")
for pfx in sorted(SERVERS):
    surface, ep, ro = SERVERS[pfx]
    names = sorted(groups.get(pfx, []))
    print(f"● {pfx}-mcp  [{ep}]  — {surface}  (read-only: {ro})  [{len(names)} tools]")
    for name in names:
        print(f"    {name}")
    print()

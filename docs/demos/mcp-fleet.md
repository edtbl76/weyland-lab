# Demo — the MCP fleet (B17+B19 Phase 3)

The operator (B66, Telegram) reasons over a **composed fleet of 6 read-only MCP servers** — one per lab subsystem —
plus its base knowledge-base tools. It selects a tool, runs it live, and answers with real data. Brain = **Haiku via
LiteLLM** (the agentic lane); tools are aggregated by the **compositor** and fronted by the **gateway** at `/mcp-fleet`.

## List the servers + tools (live)

The fleet is self-describing — this queries the compositor and prints every server and its tools as they actually are:

```
kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/list_mcp_fleet.py
```

Or ask the operator on Telegram: **"what tools do you have?"** / **"what can you tell me about the lab?"**

## A demo per tool-set (Telegram)

Each row is a prompt to send the operator + the tool it exercises + what you get back.

| Subsystem | Say to the operator | Tool exercised | You get |
|---|---|---|---|
| **trino** (lakehouse) | `list the trino catalogs` | `trino_list_catalogs` | `iceberg`, `postgresql`, `system` |
| | `what schemas are in the iceberg catalog?` | `trino_list_schemas` | the iceberg namespaces (datasets_music, dbt, …) |
| **k8s** (cluster) | `how many pods are running in the weyland namespace?` | `k8s_pods_list_in_namespace` | a running/completed/errored count |
| | `list the kubernetes namespaces` | `k8s_namespaces_list` | argocd, data-mesh, weyland, … |
| **grafana** (observability) | `what dashboards exist in grafana?` | `grafana_search_dashboards` | the dashboard list |
| | `list the grafana datasources` | `grafana_list_datasources` | Prometheus, Loki, Tempo, … |
| **postgres** | `what schemas are in postgres?` | `postgres_list_schemas` | the weyland DB schemas |
| | `check the postgres database health` | `postgres_analyze_db_health` | health/health-check summary |
| **neo4j** (graph) | `what does the neo4j graph schema look like?` | `neo4j_get_neo4j_schema` | node labels + relationship types |
| **datahub** (catalog) | `search the catalog for musicbrainz` | `datahub_search` | matching datasets/entities |

Acts stay gated: **"run the ingestion pipeline"** → a **⚠️ Confirm** prompt (nothing fires until you reply *yes*) —
the act path (`/mcp-act` + `policy.gate`) is unchanged and separate from these read tools.

## Smoke a single server directly (no operator)

Any fleet server can be exercised straight from the guard pod (swap the URL/port; postgres uses SSE — see the runbook):

```
kubectl -n weyland exec deploy/weyland-guard -- python -c 'import httpx,json; b="http://trino-mcp.weyland.svc.cluster.local:8080/mcp"; h={"Accept":"application/json, text/event-stream","Content-Type":"application/json"}; c=httpx.Client(timeout=20,follow_redirects=True); r=c.post(b,headers=h,json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"0"}}}); sid=r.headers.get("mcp-session-id"); h2={**h,**({"mcp-session-id":sid} if sid else {})}; c.post(b,headers=h2,json={"jsonrpc":"2.0","method":"notifications/initialized"}); r2=c.post(b,headers=h2,json={"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_catalogs","arguments":{}}}); d=r2.text; L=[x[5:].strip() for x in d.splitlines() if x.startswith("data:")]; print(json.loads(L[-1] if L else d))'
```

## Details
Runbook (config, gotchas, enforcement, the reusable smoke): [runbooks/mcp-fleet.md](../runbooks/mcp-fleet.md). Gateway +
composition: [runbooks/mcp-gateway.md](../runbooks/mcp-gateway.md). Operator: [runbooks/operator.md](../runbooks/operator.md).

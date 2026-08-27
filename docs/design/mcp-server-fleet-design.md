# MCP Server Fleet + Aggregation — B17+B19 Phase 3

## Why now
Phase 1 (gateway auth + actor injection) and Phase 2 (enforcing `policy.gate` + anti-spoof AuthorizationPolicy) are
live. Phase 3 = the aggregation layer (**FastMCP** server-edge composition + **Bifrost** agent-edge aggregation). Both
were correctly parked because **their value only materializes with ≥2 MCP servers** — with one (the tool-server) there
is nothing to compose or aggregate. This item *earns* that trigger by standing up a fleet of genuinely-useful MCP
surfaces the tool-server doesn't cover, then wiring the aggregation over them.

Not "build servers to justify Bifrost" — each server fills a real capability gap (agents can't query the lakehouse, the
catalog, the graph, cluster state, Grafana, or the operational cells today). Aggregation is the payoff, not the motive.

## The 6 servers
Each exposes a distinct backend as MCP tools. Prefer off-the-shelf/official servers (deploy, no build); home-grow only
where none exists. **Verify the exact image/repo + license at build time — do not assume a pinned tag here.**

| # | Server | Surface | Sourcing (verify at build) | Backend auth + mesh |
|---|--------|---------|----------------------------|---------------------|
| 1 | grafana-mcp | dashboards / Prometheus queries / alerts | official `grafana/mcp-grafana` | Grafana service-account token (Secret); in-cluster grafana svc |
| 2 | trino-mcp | lakehouse SQL over `iceberg.*` + dbt marts | community Trino MCP | reuse `trino-noauth` proxy (as Lightdash/Soda/Cube do) |
| 3 | postgres-mcp | operational + data cells, **read-only** | `crystaldba/postgres-mcp` (restricted/read-only) | STRICT-mTLS Postgres → the pod MUST be meshed |
| 4 | k8s-mcp | cluster read (pods/deploys/events) | community k8s MCP | in-cluster ServiceAccount + read-only RBAC (no act) |
| 5 | datahub-mcp | catalog search + lineage | official Acryl MCP if it exists, else home-grown over the DataHub GraphQL | DataHub PAT (Secret) |
| 6 | neo4j-mcp | graph / Cypher (read) | official `mcp-neo4j` cypher server | Bolt creds; `neo4j-bolt` DestinationRule (long-conn stall) |

### Per-server integration checklist (the repeating pattern)
1. **Source**: confirm an off-the-shelf server + license; else scope a thin home-grown FastMCP/FastAPI server.
2. **Deploy**: Deployment + Service, ns `weyland` (or `data-mesh` for mesh-native backends), Argo app entry in
   `subdir-apps.yaml`. Registry image if we build one.
3. **Backend auth**: creds via k8s Secret (gitignored `.env` convention; never committed). Read-only where the backend
   supports it (postgres-mcp, k8s-mcp, neo4j-mcp, datahub-mcp are read surfaces; only the tool-server has acts).
4. **Mesh**: join the mesh when the backend is STRICT (Postgres) or needs a DestinationRule (Neo4j Bolt). Otherwise
   PERMISSIVE/unmeshed is fine.
5. **Expose**: in-cluster svc is enough (the aggregator reaches them cluster-internally) — no per-server ingress needed.
6. **Verify**: MCP `tools/list` returns the expected tools; one representative `tools/call` returns real data.

## Aggregation architecture
```
[grafana-mcp, trino-mcp, postgres-mcp, k8s-mcp, datahub-mcp, neo4j-mcp, weyland-tool-server]
        |  (each a plain in-cluster MCP server)
        v
   FastMCP composition  ---- one composed MCP endpoint (mounts all upstreams; namespaced tool names)
        |
        v
   weyland-mcp-gateway  ---- unchanged: Keycloak Bearer -> verified actor (X-Forwarded-Consumer), one auth point
        |
        v
   agents  <---- Bifrost (agent edge): the operator (B66) + coding agents (B15) get ONE MCP-tool endpoint
```
- **FastMCP** finally does its actual job (multi-server composition/proxy) — mount the 7 servers behind one MCP surface
  with namespaced tool names (`grafana.*`, `trino.*`, …). This is the server-edge piece.
- **Gateway stays the single auth/actor choke point** — it fronts the *composed* endpoint, so we don't multiply
  Keycloak clients or AuthorizationPolicies per server. `policy.gate` still keys on the one injected actor.
- **Bifrost** is the agent-edge client: agents that can't do OAuth (B15 coding agents) point at Bifrost, which holds the
  credential and talks to the gateway — closing the "coding agents can't send a Bearer" loose end.
- **Acts stay isolated to the tool-server** — the 6 new servers are READ surfaces. The act gate / anti-spoof story is
  unchanged (only the tool-server exposes `/mcp-act`).

## Build order
Easiest off-the-shelf first to nail the deploy+auth+mesh pattern, then reuse it:
**grafana-mcp → trino-mcp → k8s-mcp → postgres-mcp → neo4j-mcp → datahub-mcp**, one at a time (validate each before the
next, per the one-step-at-a-time rule), THEN FastMCP composition, THEN Bifrost, THEN DoD (docs/diagrams/memory/backlog/Linear).

## Fleet deploy gotchas (learned from grafana-mcp #1, 2026-07-29)
Apply these to every server up front:
1. **Image tag format** — verify the real registry tag (grafana published `1.0.0`, NOT `v1.0.0`; the GitHub *release* tag had the `v`). A wrong tag → `ErrImagePull: not found`.
2. **No `/healthz`** — many MCP servers serve only the MCP endpoint (`/mcp`), not an HTTP health path. Use a **`tcpSocket`** liveness/readiness probe on the port; functional correctness is the `tools/list` smoke, not an HTTP health check.
3. **DNS-rebinding host guard** — streamable-http servers reject a `Host` header not on their allowlist (`403 forbidden: host not allowed`), default loopback-only. Pass the server's allowlist flag (grafana: `--allowed-hosts=<svc-fqdn>:<port>,...`) with the k8s **service FQDN + short forms**. Each server has its own flag/env — find it.
4. **Response framing varies** — a server may return `tools/list` as plain `application/json` OR SSE (`event:/data:` lines). The reusable smoke handles both: collect `data:` lines, else parse the raw body.
5. **Rollout overlap** — smoke *after* `rollout status` settles; an old replica (pre-fix) can still serve a request issued mid-roll and yield a stale error.

Reusable MCP smoke (from the guard pod, has httpx) — swap the base URL per server:
```
kubectl -n weyland exec deploy/weyland-guard -- python -c 'import httpx,json; b="http://<svc>.weyland.svc.cluster.local:8000/mcp"; h={"Accept":"application/json, text/event-stream","Content-Type":"application/json"}; c=httpx.Client(timeout=15); r=c.post(b,headers=h,json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}); sid=r.headers.get("mcp-session-id"); h2={**h,**({"mcp-session-id":sid} if sid else {})}; c.post(b,headers=h2,json={"jsonrpc":"2.0","method":"notifications/initialized"}); r2=c.post(b,headers=h2,json={"jsonrpc":"2.0","id":2,"method":"tools/list"}); d=r2.text; L=[x[5:].strip() for x in d.splitlines() if x.startswith("data:")]; j=json.loads(L[-1] if L else d); print("tools:",[t["name"] for t in j["result"]["tools"]])'
```

### Status
- ✅ **#1 grafana-mcp** — live, `tools/list` returns Grafana tools (read-only via `--disable-write`). 2026-07-29.
- ✅ **#2 trino-mcp** — live (`ghcr.io/tuannvm/mcp-trino:4.3.1`, `MCP_TRANSPORT=http`, **`MCP_HOST=0.0.0.0`** or it binds localhost). `list_catalogs` → `[iceberg, postgresql, system]` via the `trino-noauth` proxy as `X-Trino-User: mcp`. **Read-only defense-in-depth confirmed:** the server itself refuses writes (`TRINO_ALLOW_WRITE_QUERIES=false` default → "only SELECT/SHOW/DESCRIBE/EXPLAIN allowed") AND Ranger default-deny. No host-guard on this Go server. 2026-07-29.
- ✅ **#3 k8s-mcp** — live (`ghcr.io/containers/kubernetes-mcp-server:latest`, `--read-only --port 8080`). `namespaces_list` → real cluster. **Read-only three ways:** no write tools exposed (`--read-only`), + own SA bound to built-in `view` ClusterRole (get/list/watch, **excludes Secrets**). SSE response framing (smoke handles it). 2026-07-29.
- ✅ **#4 postgres-mcp** — live (`crystaldba/postgres-mcp:0.3.0`). **0.3.0 has only stdio/sse — no streamable-http**, so `--transport=sse --sse-host=0.0.0.0 --sse-port=8000` (SSE transport = GET /sse + POST /messages; needs a threaded reader smoke, see below). **Meshed** (STRICT Postgres) — log confirmed "connected to database". 9 tools (`list_schemas`/`execute_sql`/`analyze_db_health`…). **Read-only = `--access-mode=restricted`** → server wraps queries in Postgres READ ONLY transactions (DB-enforced). `DATABASE_URI` built via `$(PGPASSWORD)` interpolation from `weyland-postgres-secret`, `sslmode=disable` (mesh does TLS). 2026-07-29.
  - **SSE-transport smoke** (for any sse-only server): open `GET /sse` in a thread, grab the `endpoint` event's `/messages/?session_id=…` path, POST init/initialized/tools-list there, read responses off the stream. (Heredoc via `kubectl exec -i … python -`.)
- ✅ **#5 neo4j-mcp** — live (`mcp/neo4j-cypher:latest`, **FastMCP 2.13.3**, `NEO4J_TRANSPORT=http`). Endpoint is FastMCP's default **`/mcp/`** (trailing slash) — NOT `/api/mcp/` (the docs' `NEO4J_MCP_SERVER_PATH` wasn't the running default; the startup banner logs the real Server URL — always check it). tools: `get_neo4j_schema`, `read_neo4j_cypher` (**no write tool** — `NEO4J_READ_ONLY=true`). `NEO4J_MCP_SERVER_ALLOWED_HOSTS=*` (FastMCP TrustedHost guard; ClusterIP-only). Unmeshed (neo4j PERMISSIVE). 2026-07-29.
- ✅ **#6 datahub-mcp** — live (**self-built** `registry.weyland.lab/mcp-server-datahub:0.1` from the official `acryldata` PyPI package — no official HTTP image exists; `services/mcp-server-datahub/Dockerfile`). `--transport http`, **FastMCP stateless**, path **`/mcp`** (NO trailing slash → a `307` redirect, so the smoke needs `follow_redirects=True`; stateless → no `mcp-session-id`). **No `--host`/`--port` flags** → `FASTMCP_HOST=0.0.0.0` (default 127.0.0.1) + `FASTMCP_PORT`. 8 read tools (`search`/`get_lineage`/`get_entities`/`list_schema_fields`/`grep_documents`…). **Read-only default** — mutation/user/data-quality tools DISABLED (log-confirmed) unless `TOOLS_IS_MUTATION_ENABLED=true`. GMS via `datahub-token`. Unmeshed (GMS PERMISSIVE). 2026-07-29.

## ✅ FLEET COMPLETE — all 6 servers live (2026-07-29)
All read-only, all streamable-http (except postgres = sse-only on 0.3.0).

## ✅ FastMCP COMPOSITION done (2026-07-29)
`weyland-mcp-compositor` (`services/weyland-mcp-compositor/`, FastMCP 3.4.5 `create_proxy`, `k8s/mcp-servers/compositor.yaml`)
aggregates the **6 fleet servers** into one endpoint with per-server tool prefixes (`grafana_*`, `trino_*`, `k8s_*`,
`postgres_*`, `neo4j_*`, `datahub_*` — ~90 tools). **Two-endpoint topology** (gateway v4):
- `/mcp-fleet` → compositor (path-rewritten to its `/mcp`) — the 6 subsystems.
- `/mcp` → tool-server (RAG reads, **unchanged** — no regression).
- acts (`/mcp-act`, `/pipeline`, `/evals`) → tool-server (unchanged).

**KEY FINDING:** the tool-server's `fastapi-mcp` `mount_http` `/mcp` **HANGS FastMCP's proxy client** (aggregate `tools/list`
fans out to all backends with no per-upstream timeout → one bad backend hangs the whole thing). So **context is EXCLUDED**
from the compositor (`CONTEXT_URL=""`); RAG stays on the gateway `/mcp` → tool-server, and **Bifrost aggregates the two
endpoints agent-side** — the textbook split (FastMCP composes the homogeneous fleet server-side; Bifrost composes
endpoints client-side). Bisect trick: the app skips any upstream whose URL env is empty (`kubectl set env … <X>_URL=""`).
Proven end-to-end: operator token → `mcp-gateway /mcp-fleet` → compositor → 6 prefixes.

Next: **Bifrost** (agent edge), then DoD.

## Phase 3b — Bifrost (the agent edge / coding-agent MCP front door)

**Two consumer edges over ONE fleet.** The compositor + gateway `/mcp-fleet` are the *server* edge. There are two *client*
edges that consume the same tools, shaped for different consumers:

| Edge | Consumer | How it reaches the tools |
|---|---|---|
| **Chat lane** | the **operator** (B66, ours) | self-wires (langchain-mcp-adapters) → gateway `/mcp-fleet`; Haiku via LiteLLM |
| **Coding lane** | **B15 coding agents** (Cline / Cursor / Claude Code / opencode — third-party) | point at **Bifrost** → one aggregated `/mcp` |

**Why Bifrost (not just re-use the compositor):** third-party coding tools support "add an MCP server URL" but can't wire
6 servers or do the Keycloak OAuth dance. Bifrost (maximhq, self-hosted, Go) **connects to multiple upstream MCP servers
and re-exposes all their tools through one `/mcp` endpoint** with per-client **virtual-key**-scoped tool registries +
OAuth discovery that Cursor/Claude Code auto-detect. So it's a genuine *second front door*, not a re-do of the compositor.

**Design:**
- **Aggregates** (in-cluster, direct — reads only, no gateway auth needed): the **compositor** (`weyland-mcp-compositor:8000/mcp`
  → 6 subsystems) + the tool-server `/mcp` (RAG) *if it doesn't hang Bifrost's Go client like it did FastMCP's — test, drop if it does*.
- **Deploy:** `maximhq/bifrost` (Docker), port **8080**, state in `/app/data` (PVC), ns `weyland`, `k8s/bifrost/`. Web UI at
  `bifrost.weyland.lab` (Keycloak forward-auth like every UI). Upstream MCP servers configured via `config.json`/UI.
- **Downstream auth (agentic, not browser SSO):** **virtual key** — a coding agent presents `x-bf-vk`/`Authorization: Bearer vk_…`
  in its MCP client config, gets a filtered tool registry. Per-user OAuth available for clients that support it.
- **Governance intact:** reads only (fleet is read-only); acts still go gateway→tool-server `/mcp-act` w/ `policy.gate` — Bifrost never touches the act path.
- **Consumer/demo:** wire one coding agent (Cline/Cursor) at Bifrost's `/mcp` → it gets all ~90 lab tools with one URL + a VK.

**Build = deploy → configure upstreams (UI/config.json) → mint a VK → verify aggregated `tools/list` → point one coding agent at it.**

## Out of scope / guardrails
- **$0 / self-hosted / LAN** — no paid MCP hosts; off-the-shelf OSS or home-grown only.
- **Read-only servers** — no new act surfaces; the tool-server remains the only actor of side effects.
- **No per-server ingress** — aggregate internally; only the gateway is externally reachable.
- **A2A (B17)** stays a separate eval, after this.

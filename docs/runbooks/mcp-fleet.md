# MCP Server Fleet (B17+B19 Phase 3)

A fleet of **read-only** MCP servers, each exposing a lab subsystem the tool-server doesn't cover, so an agent can
query the platform through one protocol. They exist to give the aggregation layer (FastMCP composition + Bifrost) a
real job — with one MCP server there is nothing to compose. All live in ns `weyland`, dir `k8s/mcp-servers/`, Argo app
**`mcp-servers`**. All are **read surfaces only** — the tool-server remains the sole actor of side effects (its
`/mcp-act` gate + anti-spoof AuthorizationPolicy are unchanged).

## The 6 servers

| Server | Image | Surface | In-cluster URL | Read-only enforcement |
|--------|-------|---------|----------------|-----------------------|
| grafana-mcp | `grafana/mcp-grafana:1.0.0` | dashboards / Prometheus queries / alerts | `grafana-mcp:8000/mcp` | `--disable-write` |
| trino-mcp | `ghcr.io/tuannvm/mcp-trino:4.3.1` | lakehouse SQL (`iceberg.*`, dbt marts) | `trino-mcp:8080/mcp` | server `TRINO_ALLOW_WRITE_QUERIES=false` **+** Ranger default-deny |
| k8s-mcp | `ghcr.io/containers/kubernetes-mcp-server:latest` | cluster read (pods/events/nodes) | `k8s-mcp:8080/mcp` | `--read-only` **+** SA→`view` ClusterRole (no Secrets) |
| postgres-mcp | `crystaldba/postgres-mcp:0.3.0` | Postgres (operational + app cells) | `postgres-mcp:8000` (**SSE**) | `--access-mode=restricted` (Postgres READ ONLY txns) |
| neo4j-mcp | `mcp/neo4j-cypher:latest` | graph / Cypher | `neo4j-mcp:8000/mcp/` | `NEO4J_READ_ONLY=true` (no write tool) |
| datahub-mcp | `registry.weyland.lab/mcp-server-datahub:0.1` (self-built) | catalog search + lineage | `datahub-mcp:8000/mcp` | mutation tools disabled by default |

Each proven via MCP `tools/list` (+ a real read call, and a write-denial probe where the server exposes a query tool).

> **A seventh server is available but not deployed: the code graph.** `graphify --mcp` is a stdio MCP
> server exposing this repo's AST graph (`affected`, `god-nodes`, `query`), which would let the operator
> and the Realm agents ask code-structure questions — something no server in the fleet can answer today.
> Not built because nothing has needed it. Tracked as **EMA-208 (Low)**; see
> `docs/concepts/graphify-adoption.md`.

> **Two MCP planes — the fleet is not the only place MCP lives.** This fleet is the **shared, read-only,
> in-cluster** plane: servers reached through the gateway/FastMCP compositor by the operator and the Realm
> agents. There is a second, deliberately separate plane: **local, agent-side MCP** wired into a coding
> agent's own `.mcp.json` (stdio, `uvx`/local process), running *beside* the agent on the workstation.
> **Serena** (B166 — LSP→MCP code intelligence) lives there, **not** in this fleet, and that is by design:
> it is **editing-capable** (`replace_symbol_body`, `rename_symbol`, `insert_after_symbol`…), **per-project**
> and **stateful** (a language server + `.serena/` cache indexed to one repo) — the opposite of a shared
> read-only service. The rule of thumb: **shared + read-only + in-cluster → the fleet; per-project +
> editing + beside-the-agent → local `.mcp.json`.** Serena would only join the fleet if the **B66 operator**
> (which reaches tools through the gateway, not a local `.mcp.json`) needed code navigation — and then only
> a **read-only subset** (`find_symbol`, `find_referencing_symbols`, `get_symbols_overview`), never the
> editing tools. See `docs/runbooks/code-intelligence.md` § Serena.

## Connectivity notes
- **trino-mcp** → the `trino-noauth` proxy (`trino-noauth.data-mesh.svc:8080`) as `X-Trino-User: mcp` — the same no-auth
  path dbt/Soda/Cube use. Ranger is default-deny, so `mcp` reads only what it's granted and can never write.
- **postgres-mcp** is **meshed** (`sidecar.istio.io/inject`) — Postgres is STRICT-mTLS; a non-meshed client gets opaque
  ECONNRESET. The mesh does TLS, so the connection is plaintext (`sslmode=disable`). `DATABASE_URI` is composed via
  `$(PGPASSWORD)` interpolation from `weyland-postgres-secret` (password never inlined).
- **k8s-mcp** has its own SA `k8s-mcp` bound to the built-in **`view`** ClusterRole (get/list/watch, excludes Secrets).
- **neo4j-mcp** → `bolt://neo4j.weyland.svc:7687` (`neo4j-secret/password`); unmeshed (neo4j PERMISSIVE, short queries).
- **datahub-mcp** → GMS `datahub-datahub-gms.data-mesh.svc:8080` with `datahub-token`; built from the official PyPI
  package (no official HTTP image) — `services/mcp-server-datahub/Dockerfile`.

## Deploy gotchas (learned building the fleet)
1. **Image tag format** — verify the *registry* tag, not the GitHub release tag: grafana published `1.0.0` (not `v1.0.0`),
   tuannvm `4.3.1` (not `v4.3.1`). A wrong tag → `ErrImagePull: not found`.
2. **No `/healthz`** — most MCP servers serve only the MCP endpoint. Use **`tcpSocket`** liveness/readiness probes;
   functional correctness is the `tools/list` smoke, not an HTTP health path.
3. **Bind address** — several default to `127.0.0.1` (unreachable in-pod): set `MCP_HOST=0.0.0.0` (trino), `--sse-host=0.0.0.0`
   (postgres), `NEO4J_MCP_SERVER_HOST=0.0.0.0`, `FASTMCP_HOST=0.0.0.0` (datahub). grafana's Go server binds `0.0.0.0` already.
4. **DNS-rebinding host guard** — streamable-http servers may reject a `Host` not on their allowlist (`403 forbidden: host
   not allowed`). Set the allowlist: grafana `--allowed-hosts=<svc-fqdn>,…`; neo4j `NEO4J_MCP_SERVER_ALLOWED_HOSTS=*`
   (ClusterIP-only → `*` is safe). trino/datahub had none.
5. **Endpoint path varies** — `/mcp` (grafana, datahub — datahub has **no trailing slash**, stateless → a `307` redirect,
   so a client needs `follow_redirects=True`), `/mcp/` (neo4j, FastMCP default), `/sse`+`/messages` (postgres SSE). **Always
   read the startup banner for the real Server URL** — the neo4j docs' `/api/mcp/` was wrong; the banner said `/mcp/`.
6. **Response framing** — `tools/list` may come back as plain JSON or SSE (`data:` lines). The smoke handles both.
7. **Rollout overlap** — smoke *after* `rollout status` settles; an old replica can serve a mid-roll request and return a
   stale error.

## Verify — the reusable MCP smoke
From the guard pod (has httpx). Swap the base URL per server; datahub needs `follow_redirects=True`; postgres (SSE) uses
the threaded reader below.

```
kubectl -n weyland exec deploy/weyland-guard -- python -c 'import httpx,json; b="http://<svc>.weyland.svc.cluster.local:<port>/<path>"; h={"Accept":"application/json, text/event-stream","Content-Type":"application/json"}; c=httpx.Client(timeout=15, follow_redirects=True); r=c.post(b,headers=h,json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}); sid=r.headers.get("mcp-session-id"); h2={**h,**({"mcp-session-id":sid} if sid else {})}; c.post(b,headers=h2,json={"jsonrpc":"2.0","method":"notifications/initialized"}); r2=c.post(b,headers=h2,json={"jsonrpc":"2.0","id":2,"method":"tools/list"}); d=r2.text; L=[x[5:].strip() for x in d.splitlines() if x.startswith("data:")]; j=json.loads(L[-1] if L else d); print("tools:",[t["name"] for t in j["result"]["tools"]])'
```

**SSE transport** (postgres-mcp): open `GET /sse` in a thread, read the `endpoint` event's `/messages/?session_id=…`
path, POST init/initialized/tools-list there, read responses off the stream (heredoc via `kubectl exec -i … python -`).

## Composition + the operator (done 2026-07-30)
- **`weyland-mcp-compositor`** (`services/weyland-mcp-compositor/`, FastMCP `create_proxy`) aggregates the **6 servers**
  into one endpoint, tools namespaced `grafana_*`/`trino_*`/… (~90). The gateway routes **`/mcp-fleet` → compositor**;
  `/mcp` still → tool-server (RAG). The tool-server's own `fastapi-mcp` is NOT composed (its mount hangs FastMCP's proxy
  client) — RAG stays a separate endpoint; that's fine, agent-side aggregation is Bifrost's job.
- **Shared agent memory joins the fleet READ-ONLY (B182, 2026-10-03).** Upstream `memory` → Basic Memory on rogueone
  (`MEMORY_URL` in `k8s/mcp-servers/compositor.yaml`). Upstreams + allowlists now live in `config.py` (unit-tested,
  `tests/test_config.py`); a `ReadOnlyAllowlist` middleware in `app.py` **hides AND refuses** any memory tool not on
  the allowlist — 7 pass (`memory_search_notes`, `memory_read_note`, `memory_view_note`, `memory_read_content`,
  `memory_build_context`, `memory_recent_activity`, `memory_list_directory`); write/delete/move/project tools and any a
  future version adds stay out. FastMCP 3.4.5's per-server `tools`/`include_tags` config could NOT do this (the tag
  is not applied; include_tags hid all 21 — observed). With one upstream FastMCP does not prefix tool names; with
  several it does (`memory_*`). Proven in a real container: 7 listed, `memory_write_note` refused, search works.
  **Memory searches through the fleet are SEMANTIC (2026-10-04)** — `config.rewrite_arguments` turns a
  `memory_search_notes` call asked as default/`text`/`hybrid` into `search_type: semantic`; `title`/`permalink` (exact
  lookups) and an explicit `semantic`/`vector` pass as asked. Why, measured: for "rogueone GPU freeze" the answering note
  (`rogueone-gpu-freeze-vram`) is #1 by semantic search and absent from the top 10 by text and by the default hybrid,
  whose full-text half dominates short keyword queries — what a small model writes (the operator's 7B also picks
  `text` on its own). Proven in a real container: rewritten calls rank it #1; an un-rewritten control does not. Only the
  fleet is affected — coding agents reach Basic Memory through Bifrost, untouched.
  It also **drops frontmatter filters our notes never carry** (`tags`, `status`, `metadata_filters`, `categories`,
  `note_types`, `entity_types` — 0 of 215 notes have tags): live 2026-10-04 the operator's 7B passed `tags="reason"`,
  got nothing, and answered "no notes" while the answering note ranked #1 unfiltered. `after_date`/`project`/paging stay.
  The compositor's `fastmcp` is now pinned (`requirements.in/.txt`; it was unpinned) and the image is CI-built
  (`images.tsv`, 2026-10-03).
- **The operator (B66) uses the fleet.** It loads the `/mcp-fleet` tools via `langchain-mcp-adapters` (per-request
  Keycloak token via a custom `httpx.Auth`), sanitizes their schemas (`fleet._sanitize_schema` — MCP servers emit
  inconsistent schemas), and binds them flat (`ainvoke` — MCP tools are async-only). `FLEET_ROUTING=1` switches to
  6 subsystem routers for a weaker local brain.
- **The operator reads the fleet ONCE, at startup** (`[fleet] loaded N read tools` in its log). A compositor change
  (new upstream, new allowlist) does not reach the operator until it restarts. Live 2026-10-03: compositor and operator
  shipped together and both pods started in the same second; the operator listed the fleet from the OLD compositor pod
  still serving during the rolling update, and loaded 95 tools instead of 102. Check the count, and if it is stale,
  restart the operator by deleting its pod (the Deployment recreates it; unlike `rollout restart`, this leaves no
  template drift for Argo's selfHeal to revert):

  [mother]
  ```
  kubectl -n weyland delete pod -l app=weyland-operator && kubectl -n weyland rollout status deploy/weyland-operator --timeout=300s && sleep 20 && kubectl -n weyland logs deploy/weyland-operator | grep "\[fleet\] loaded"
  ```
  Expect `[fleet] loaded 102 read tools` (95 cluster tools + 7 `memory_*`).

## The LLM lane — two-lane rule (learned here, 2026-07-30)
The operator's brain is **Haiku via LiteLLM**, NOT the MLflow AI Gateway. The MLflow Gateway *normalizes/validates*
requests (great for chat; its strict tool-schema validation **shreds** heterogeneous MCP tool schemas — proven by a
direct-to-Anthropic A/B). LiteLLM is a *transparent* passthrough (tools + tool_calls survive) and is still governed
(spend tracking + egress valve). So: **agentic/tool-calling → LiteLLM; chat/RAG/eval/judge → MLflow AI Gateway.**
Guardrails for the agent live at its EDGE (`weyland-guard` input/output + the act confirm-step), never inline in the LLM path.

## Demo + list
- **List servers + tools (live):** `kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/list_mcp_fleet.py`
- **Per-tool-set demos** (Telegram prompts): [demos/mcp-fleet.md](../demos/mcp-fleet.md)

## What's next
- **Bifrost** — the agent edge (aggregate `/mcp` + `/mcp-fleet` for agents that can't OAuth; B15 coding agents).
- **B109** — Grafana dashboard audit driven through grafana-mcp (first real application).

Design: `../design/mcp-server-fleet-design.md`. Relates [runbooks/mcp-gateway.md](mcp-gateway.md), [runbooks/operator.md](operator.md), [[b17-b19-mcp-gateway]].

# Bruno collection — weyland lab APIs (B104)

[Bruno](https://usebruno.com) is a $0, OSS, offline API client whose collections are **plain files
committed to git** (`.bru`) — no cloud account, no LAN-hostile sync. It complements the machine-readable
API-lifecycle catalog (`apis.yaml`, B155): that governs owner/version/status; this is the *executable*
client + a runnable smoke of the request-serving plane.

## Layout

```
bruno/weyland/
  bruno.json                     # collection manifest
  environments/lan.bru           # base URLs for 9 services + gw_key secret var
  tool-server/   health · ready · status · metrics · models · backend-{pgvector,qdrant,weaviate,neo4j,ollama} · context-search (functional)
  gateway/       readiness · liveliness              (LiteLLM)
  qdrant/        healthz · readyz · livez · collections · metrics
  weaviate/      ready · live · meta
  neo4j/         discovery
  ollama/        tags
  rag-embed/     health
  clickhouse/    ping
  mlflow-gateway/ health
  authenticated/ gateway-models  # bearer example (needs gw_key; excluded from the keyless run)
```

Base URLs are the LAN NodePorts / CT IPs from [../../docs/api.md](../../docs/api.md).

## Scope (what's covered, and what's deliberately not)

**Covered:** every **LAN-reachable, read/health, no-auth** endpoint of the request-serving + data-backend
surface — the tool-server platform boundary (10 endpoints incl. all 5 vector backends + one real
retrieval POST), the LiteLLM gateway, Qdrant, Weaviate, Neo4j, Ollama, rag-embed, ClickHouse, and the
MLflow gateway. 26 requests, 56 assertions, all green against live services.

**Deliberately excluded** (with reasons, so "coverage" is honest and bounded):
- **Mutating / act endpoints** (`/pipeline/trigger`, `/evals/run`, `/context/ask` — LLM cost) — a smoke
  collection should not fire side-effects; `/context/search` is included because it is read-only.
- **In-cluster-only services** (weyland-guard, weyland-agent, operator, Trino, the 6-server MCP fleet) —
  no LAN NodePort; a Bruno run from a workstation can't reach a ClusterIP.
- **Browser-SSO UIs** (Grafana, Argo, Dagster, …) — forward-auth, not API clients.
- **Auth'd data queries** (ClickHouse `SELECT`, Neo4j Cypher) — need per-store credentials; only the
  unauthenticated health/ping/discovery endpoints are asserted.

## Run it

Open `bruno/weyland` in the Bruno app, or headless via the CLI (`bru`):

```
cd bruno/weyland
# keyless read surface — 26 requests / 56 assertions, all green:
npx --yes @usebruno/cli run tool-server gateway qdrant weaviate neo4j ollama rag-embed clickhouse mlflow-gateway --env lan
# the authenticated example:
npx --yes @usebruno/cli run authenticated --env lan --env-var gw_key=$LITELLM_API_KEY
```

A fast "is the read surface answering correctly" check that pairs with the perf baseline
([[perf-baseline]], which measures throughput on the same serving plane).

## Add a request

Drop a `.bru` file in the relevant folder (see `tool-server/health.bru` for the shape: `meta` / `get` /
`assert`). Assert on `res.status` and on JSON fields (`res.body.<field>`); for text bodies assert
`res.body: contains <token>`. Anything needing a bearer goes under `authenticated/` and reads a secret
var so it stays out of the keyless run. Keep base URLs in `environments/lan.bru`, never inline.

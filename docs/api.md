# Weyland — API & Endpoint Inventory

Live registry of **every API/endpoint in the lab**. Manual precursor to **B12** (aggregated
OpenAPI portal). Keep this updated as endpoints are added/changed (see [[feedback-keep-api-hosts-updated]]).

Hosts & access users: [hosts.md](hosts.md). `mother` = 192.168.1.243, CTs by IP (or the new
`*.weyland.lab` names once CoreDNS picks them up).

`✅ OpenAI /v1` = speaks the OpenAI API shape (the endpoints a future portal/agent can drop into).

## Model serving (inference / STT)

| Service | Host | Endpoint | OpenAI? | Notes |
|---|---|---|---|---|
| **Ollama** (LLM) | ollama CT 102 | `http://ollama.weyland.lab:11434/v1` (`192.168.1.244`) | ✅ | 6 models; `num_thread 8`. See [runbooks/model-serving-ollama.md](runbooks/model-serving-ollama.md). |
| **whisper shim** (STT) | whisper CT 103 | `http://whisper.weyland.lab:9000/v1/audio/transcriptions` (`192.168.1.246`) | ✅ | OpenAI-compatible adapter → whisper.cpp. See [runbooks/transcription-whisper.md](runbooks/transcription-whisper.md). |
| **whisper-server** (STT, native) | whisper CT 103 | `http://whisper.weyland.lab:8080/inference` (`192.168.1.246`) | ✗ | Raw whisper.cpp multipart endpoint. |
| **vLLM** (LLM, GPU) | rogueone | `http://rogueone:8000/v1` | ✅ | On-demand; serves Qwen. GPU path. |

## Tool server (platform service boundary)

`mother`, NodePort **30080** → `http://mother:30080` (FastAPI: `/docs`, `/openapi.json`).

| Route | Method | Purpose |
|---|---|---|
| `/health` `/ready` `/status` | GET | liveness / readiness / consolidated status (incl. `llm`) |
| `/context/search?backend=<pgvector\|qdrant\|weaviate\|neo4j>` | POST | vector retrieval |
| `/context/ask` | POST | **RAG** — retrieve → local LLM answer (per-request `model`) |
| `/models` | GET | list selectable Ollama models |
| `/pgvector/health` `/qdrant/health` `/weaviate/health` `/neo4j/health` `/ollama/health` | GET | per-backend health |
| `/pipeline/trigger` | POST | fire Dagster `launchRun` |
| `/evals/run` · `/evals/score` | POST | B4: trigger eval matrix / judge-panel scoring |
| `/evals/runs` · `/evals/leaderboard` | GET | B4: list eval runs / panel-averaged leaderboard (`?run_id=`) |
| `/mcp` | MCP | **B2 system-view MCP server** (Streamable HTTP via `fastapi-mcp`) — read-only tools: `status`, `context_search`, `context_ask`, `list_models`. Consumers: **Hermes** (registered in `~/.hermes/config.yaml`), **Claude Code** (registered via `claude mcp add weyland --transport http http://192.168.1.243:30080/mcp`, validated 2026-06-14). [runbooks/agent-hermes.md](runbooks/agent-hermes.md) |

## Data backends (mother, NodePort)

| Service | Endpoint | Notes |
|---|---|---|
| Qdrant HTTP | `http://mother:30083` | collection `weyland_chunks` |
| Qdrant gRPC | `mother:30084` | |
| Weaviate | `http://mother:30087` | gRPC 50051; class `WeylandChunk` |
| Neo4j HTTP | `http://mother:30085` | browser/REST |
| Neo4j Bolt | `neo4j://mother:30086` | APOC enabled |
| Postgres/pgvector | `weyland-postgres.weyland.svc:5432` | **in-cluster only** (no NodePort) |

## Gateways

| Service | Endpoint | Notes |
|---|---|---|
| APISIX gateway | `http://mother:30090` | API gateway data plane |
| APISIX dashboard | `https://apisix.weyland.lab` | via Traefik TLS |

## Web UIs (Traefik TLS, `*.weyland.lab` → mother `192.168.1.243`)

mkcert wildcard cert; resolve from rogueone (`/etc/hosts`) or via CoreDNS. Shared dev creds.

| UI | URL |
|---|---|
| **Open WebUI** (voice/chat → Ollama + whisper) | `https://chat.weyland.lab` |
| Grafana | `https://grafana.weyland.lab` |
| Dagster | `https://dagster.weyland.lab` |
| n8n | `https://n8n.weyland.lab` |
| Headlamp (k8s UI) | `https://headlamp.weyland.lab` |
| Filestash (MinIO browser) | `https://files.weyland.lab` |

> **Headlamp login** uses a Kubernetes **ServiceAccount bearer token**, *not* the shared dev password.
> A persistent token is stored in a Secret — retrieve and decode it (on mother):
> ```
> kubectl get secret -A | grep -i headlamp        # find the secret + namespace
> kubectl get secret <name> -n <ns> -o jsonpath='{.data.token}' | base64 -d ; echo
> ```
> Paste the decoded JWT into Headlamp's token login. (Persistent = doesn't expire like
> `kubectl create token`; same command always returns it until the SA/Secret is rotated.)

## Object storage (MinIO)

| Service | Endpoint | Notes |
|---|---|---|
| MinIO S3 API | `https://s3.weyland.lab` | S3-compatible; mc on rogueone. See [runbooks/storage-minio.md](runbooks/storage-minio.md). |
| MinIO console | `https://minio.weyland.lab` | community console stripped — use Filestash instead |

## Infrastructure

| Service | Endpoint | Notes |
|---|---|---|
| CoreDNS (LAN resolver) | `mother:53` | authoritative for `weyland.lab`; forwards else to 1.1.1.1/9.9.9.9 |

## Metrics / scrape targets (B5 Phase 2b)

Prometheus-format `/metrics` endpoints. Scraped **in-cluster** by Prometheus (ns `monitoring`) over the
ClusterIP path below — the human-facing view is **Grafana** (`grafana.weyland.lab`). The raw endpoints are
not meant for direct browsing. ServiceMonitors: `k8s/monitoring/servicemonitors.yaml`.

| Emitter | In-cluster scrape target | Path | Direct LAN access |
|---|---|---|---|
| Qdrant | `qdrant.weyland.svc:6333` | `/metrics` | `http://mother:30083/metrics` (NodePort) |
| CoreDNS | `weyland-lan-dns.weyland.svc:9153` | `/metrics` | `http://mother:9153/metrics` (LoadBalancer) |
| Weaviate | `weaviate.weyland.svc:2112` | `/metrics` | NodePort auto-assigned (no fixed port) |
| APISIX | `weyland-apisix.weyland.svc:9091` | `/apisix/prometheus/metrics` | NodePort auto-assigned (no fixed port) |

Stack-internal targets (Prometheus, Alertmanager, Grafana, node-exporter, kube-state-metrics, kubelet,
cAdvisor) are scraped by the chart's own ServiceMonitors — not listed here.

> **Prometheus UI is not ingressed** — view targets/PromQL via
> `kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090`. Only Grafana is
> TLS-fronted. (Follow-up if a browsable Prometheus is wanted.)

---
**Conventions:** standalone CTs (ollama/whisper) use their reserved IPs or `*.weyland.lab` names
(added to CoreDNS). k3s services use `mother:<NodePort>` or `*.weyland.lab` (Traefik). Internal-only
services use cluster DNS (`*.weyland.svc`).

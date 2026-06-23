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
| **LiteLLM gateway** (hosted models) | mother (NodePort 30400) | `http://mother:30400/v1` (`192.168.1.243`) | ✅ | Fronts **every Gemini + OpenRouter** model (wildcard) behind one endpoint; Bearer = `LITELLM_MASTER_KEY`. Aliases `gemini-flash`/`gemini-pro`. Human-gated egress (valve) + spend alerts. Catalog of reachable models in Postgres `model_catalog`. See [runbooks/model-gateway.md](runbooks/model-gateway.md). |

## Tool server (platform service boundary)

`mother`, NodePort **30080** → `http://mother:30080` (FastAPI: `/docs`, `/openapi.json`).

| Route | Method | Purpose |
|---|---|---|
| `/health` `/ready` `/status` | GET | liveness / readiness / consolidated status (incl. `llm`) |
| `/metrics` | GET | **B14** Prometheus exposition — guardrail shadow verdicts + validator latency (plain route, no trailing slash) |
| `/context/search?backend=<pgvector\|qdrant\|weaviate\|neo4j>` | POST | vector retrieval (B14 `input` guardrail hook: injection) |
| `/context/ask` | POST | **RAG** — retrieve → local LLM answer (per-request `model`); B14 `input` hook (injection) + `output` hook (toxicity, grounding) |
| `/models` | GET | list selectable Ollama models |
| `/pgvector/health` `/qdrant/health` `/weaviate/health` `/neo4j/health` `/ollama/health` | GET | per-backend health |
| `/pipeline/trigger` | POST | fire Dagster `launchRun` (B14 `act` hook: audited; exposed via `/mcp-act`) |
| `/evals/run` · `/evals/score` | POST | B4: trigger eval matrix / judge-panel scoring (B14 `act` hook: audited; exposed via `/mcp-act`) |
| `/evals/runs` · `/evals/leaderboard` | GET | B4: list eval runs / panel-averaged leaderboard (`?run_id=`) |
| `/mcp` | MCP | **B2 system-view MCP server** (Streamable HTTP via `fastapi-mcp`) — read-only tools: `status`, `context_search`, `context_ask`, `list_models`. Consumers: **Hermes** (registered in `~/.hermes/config.yaml`), **Claude Code** (registered via `claude mcp add weyland --transport http http://192.168.1.243:30080/mcp`, validated 2026-06-14). [runbooks/agent-hermes.md](runbooks/agent-hermes.md) |
| `/mcp-act` | MCP | **B14 read+act** act-tool surface (separate mount): `pipeline/trigger`, `evals/run`, `evals/score`. Every call audited by the `act` hook (`policy.audit`, shadow) → `guardrail_verdicts`. **Consumer: Hermes only** (the resident operator); **Claude Code stays read-only on `/mcp`** (builder lane — see [runbooks/agent-hermes.md](runbooks/agent-hermes.md)). Gateway (B17+B19) fronts it with auth (`X-Forwarded-Consumer` → `actor`). |

## Data backends (mother, NodePort)

| Service | Endpoint | Notes |
|---|---|---|
| Qdrant HTTP | `http://mother:30083` | collection `weyland_chunks` |
| Qdrant gRPC | `mother:30084` | |
| Weaviate | `http://mother:30087` | gRPC 50051; class `WeylandChunk` |
| Neo4j HTTP | `http://mother:30085` | browser/REST |
| Neo4j Bolt | `neo4j://mother:30086` | APOC + GDS enabled |
| NeoDash | `http://mother:30088` | Neo4j dashboard/viz UI (connect to Bolt `:30086`); see [runbooks/aidlc-kb-ingest.md](runbooks/aidlc-kb-ingest.md) |
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
| **LiteLLM** (model gateway admin UI / `/ui`) | `https://litellm.weyland.lab` |
| **Kiali** (Istio mesh graph + mTLS, **read-only**, dev-password; traces from Tempo) | `https://kiali.weyland.lab` |
| Grafana (metrics + logs (Loki) + traces (Tempo) + alerts (Alertmanager, incl. **Loki-ruler log alerts**) — Explore/Drilldown) | `https://grafana.weyland.lab` |
| **GlitchTip** (error tracking — Sentry-SDK-compatible; own login) | `https://glitchtip.weyland.lab` |
| **OpenCost** (k8s cost allocation — custom on-prem pricing; LAN-only) | `https://opencost.weyland.lab` |
| **Woodpecker CI** (CI/CD — GitHub OAuth login; k8s backend; manual/cron triggers) | `https://woodpecker.weyland.lab` |
| **Argo CD** (GitOps CD — local admin; app-of-apps, 28 apps) | `https://argocd.weyland.lab` |
| **Platform Docs** (MkDocs Material — runbooks/architecture/concepts; browsable+searchable, Mermaid; B59, replaced Backstage TechDocs) | `https://docs.weyland.lab` |
| Dagster | `https://dagster.weyland.lab` |
| n8n | `https://n8n.weyland.lab` |
| Headlamp (k8s UI) | `https://headlamp.weyland.lab` |
| Filestash (MinIO browser) | `https://files.weyland.lab` |
| ~~weyland IDP (Backstage, `idp.weyland.lab`)~~ — **RETIRED 2026-06-22 (B59)**; replaced by **Port.io** catalog + **`docs.weyland.lab`** | — |
| **Port.io** (IDP — SaaS; **launcher/catalog**, not status board) | `https://app.port.io` — EU org; **Launcher** dashboard (`endpoint` bp). Integrations: K8s, Istio, GitHub, Linear, Unleash (`feature_flag`), SonarQube (`code_quality`), Trivy+Semgrep (`security_scan`) |
| **MLflow** (experiment tracking + model registry; B10+B16, dev-password) | `https://mlflow.weyland.lab` |
| **Uptime Kuma** (live status board — own auth; **25 monitors**, Telegram paging; Port webhook retired) | `https://kuma.weyland.lab` |
| **Linear** (roadmap/task board — SaaS; Claude via MCP, Port ingests for status) | `https://linear.app/emangini` — projects: Weyland Lab / Stud.IO / Service Transformation |
| **Unleash** (feature flags; OSS self-hosted, own login admin/dev-pass; → Port `feature_flag` webhook) | `https://unleash.weyland.lab` — Python SDK for tool-server/Hermes; see [runbooks/unleash.md](runbooks/unleash.md) |
| **SonarQube** (code quality / static analysis; own login; → Port `code_quality` webhook) | `https://sonarqube.weyland.lab` — meshed Postgres backend; on-demand scan Jobs (+ Trivy/Semgrep). See [runbooks/code-quality.md](runbooks/code-quality.md) |

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
| Tool server (B14 guardrails) | `weyland-tool-server.weyland.svc:8080` | `/metrics` | `http://mother:30080/metrics` (NodePort) |
| LiteLLM gateway | `litellm.weyland.svc:4000` | `/metrics` | `http://mother:30400/metrics` (NodePort) |
| MinIO | `minio.minio.svc:9000` | `/minio/v2/metrics/cluster` | in-cluster only (`MINIO_PROMETHEUS_AUTH_TYPE=public`, no token) |
| Proxmox VE (pve-exporter) | `pve-exporter.monitoring.svc:9221` | `/pve?target=192.168.1.232` | per-node/VM/CT metrics; read-only PVEAuditor token. Grafana dashboard #10347. See [runbooks/observability.md](runbooks/observability.md) |

Stack-internal targets (Prometheus, Alertmanager, Grafana, node-exporter, kube-state-metrics, kubelet,
cAdvisor) are scraped by the chart's own ServiceMonitors — not listed here.

> **Tool-server `/metrics` (B14):** emits `guardrail_verdicts_total` + `guardrail_validator_latency_ms`.
> Its ServiceMonitor (`weyland-tool-server`) is defined in `k8s/monitoring/servicemonitors.yaml` alongside
> the other four — `kubectl apply` it to start the scrape. The `guardrail_verdicts` Postgres table is the
> durable record (and the basis for the future B1 data product); `/metrics` is the live counter view.

> **Prometheus UI is not ingressed** — view targets/PromQL via
> `kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090`. Only Grafana is
> TLS-fronted. (Follow-up if a browsable Prometheus is wanted.)

---
**Conventions:** standalone CTs (ollama/whisper) use their reserved IPs or `*.weyland.lab` names
(added to CoreDNS). k3s services use `mother:<NodePort>` or `*.weyland.lab` (Traefik). Internal-only
services use cluster DNS (`*.weyland.svc`).

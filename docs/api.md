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
| Trino (federation query) | `jdbc:trino://trino.data-mesh.svc:8080` (in-cluster); UI `trino.weyland.lab` | **B65 Tier-2** — native-Nessie `iceberg` + `postgresql` catalogs; user any / no password; IntelliJ via k8s port-forward; web UI is monitoring-only. See [runbooks/trino.md](runbooks/trino.md). |
| GizmoSQL (DuckDB Flight SQL) | `jdbc:arrow-flight-sql://mother:31337?useEncryption=false` (NodePort — IDEA via the Arrow Flight SQL JDBC driver); `grpc+tcp://gizmosql.data-mesh.svc:31337` (in-cluster — `emit_duckdb`) | **B65 Tier-2 #2** — DuckDB single-node OLAP over the lakeFS Parquet; user `weyland` / dev password (URL params); meshed (mTLS in-cluster, plaintext app). DuckDB JDBC is embedded-only → Flight SQL gives a real host:port. See [runbooks/gizmosql.md](runbooks/gizmosql.md). |
| Superset (BI) | `https://superset.weyland.lab` (UI + API); `http://superset.data-mesh.svc:8088` (in-cluster) | **B65 Tier-2 #3** — BI/SQL exploration over Trino + Postgres. Keycloak OIDC login. Shared Valkey cache. DataHub native source ingestion. See [runbooks/superset.md](runbooks/superset.md). |
| Valkey (shared cache) | `valkey.data-mesh.svc:6379` (in-cluster only) | Shared data-mesh cache (BSD Redis fork). Used by Superset (cache + Celery). IntelliJ via k8s port-forward + DataGrip "Redis" data source. |
| TimescaleDB (time-series) | `timescaledb.data-mesh.svc:5432` (in-cluster); IntelliJ via k8s port-forward | **B65 Tier-2 #4** — Postgres extension for time-series; 5 hypertables (eval_scores_ts, guardrail_verdicts_ts, dagster_run_durations, unleash_feature_metrics, datahub_ingestion_runs); db `timeseries`, user `weyland` / dev password. See [runbooks/timescaledb.md](runbooks/timescaledb.md). |
| MySQL (health/wellness) | `mysql.data-mesh.svc:3306` (in-cluster); IntelliJ via k8s port-forward | **B65 Tier-2 #5** — health datasets, hydrated from silver Parquet (data-store-mageddon, 2026-07-01). 6 databases = the grid `MySQL=Y` set: NHANES, Big Five, WHO GHO, CDC Physical Activity, BRFSS, NHIS (USDA + Open Food Facts are `MySQL=N`; NHIS replaced UK Biobank). 32 tables (dataset→db, parquet file→table). user `weyland` / dev password. See [runbooks/datasets-hydration.md](runbooks/datasets-hydration.md). |

> **Not behind Traefik, not Keycloak-gated** — these are databases/APIs reached by code (the tool-server, clients), not browsers. They're exposed via **NodePort + the APISIX gateway**, auth'd at the API/DB layer (Neo4j login, Qdrant/Weaviate keys/network). Keycloak SSO gates browser UIs only.

## Gateways

| Service | Endpoint | Notes |
|---|---|---|
| APISIX gateway | `http://mother:30090` | **Active API/data-plane gateway** — live routes front the tool-server `/context` + `/pipeline` and the qdrant/weaviate/neo4j backends (same backends the NodePorts expose directly). **Not Keycloak-gated** — API-client front door, auth at the gateway/API layer, not browser SSO. |
| APISIX dashboard | `https://apisix.weyland.lab` | via Traefik TLS |

## Identity / SSO (Keycloak — B1.1, 2026-06-24)

Central IdP for the lab — replaced the scattered dev-password / per-app logins. **Keycloak** (`keycloak.weyland.lab`, `weyland` realm, k8s + meshed Postgres) is the OIDC provider; realm + clients codified in `tofu/keycloak/`. Apps fall into three buckets:
- **OIDC (native, true single login):** Grafana, GlitchTip, Open WebUI — hold a Keycloak client + speak OIDC directly. (MinIO's console is OIDC-capable but its community build is stripped → not used.)
- **Forward-auth (Keycloak gate in front) — EVERY other browser UI** (extended 2026-06-25): MLflow, Kiali, filestash, Nessie, lakeFS, Unleash, SonarQube, Uptime-Kuma, Dagster, LiteLLM-UI, docs-site, APISIX-dashboard, OpenCost, n8n, Woodpecker, Argo CD, Headlamp. `traefik-forward-auth` (`auth.weyland.lab`) gates the ingress; one Keycloak session covers all (`COOKIE_DOMAIN=weyland.lab`). Cross-ns middleware refs are blocked, so each protected ns gets a local `traefik-forward-auth` Middleware. **Caveat:** forward-auth gates *access* — it does NOT replace an app's own login, so own-login apps (Unleash, SonarQube, n8n, Woodpecker…) are **double-login** (Keycloak *then* their login); apps with no own login (Dagster, OpenCost, filestash) are clean single-login.
- **NOT Keycloak-gated by design** (API/DB clients, not browsers — you can't browser-SSO a database/API call): the **S3 API** (`s3.weyland.lab`), the **data backends** (qdrant/weaviate/neo4j NodePorts), and the **APISIX gateway** (`mother:30090`). These auth at the API/DB layer. Keycloak itself + `auth.weyland.lab` stay open too (they *are* the gate). Woodpecker keeps its GitHub-forge login *behind* the new Keycloak gate.

| Service | URL | Notes |
|---|---|---|
| **Keycloak** (IdP) | `https://keycloak.weyland.lab` | `weyland` realm; bootstrap admin `admin`. End-session: `/realms/weyland/protocol/openid-connect/logout` |
| **traefik-forward-auth** (forward-auth gate) | `https://auth.weyland.lab` | Gates MLflow/Kiali/filestash. **Single logout** for all forward-auth apps: `https://auth.weyland.lab/_oauth/logout` (clears the forward-auth cookie *and* ends the KC session) |

> **Login:** `emangini` / `weyland_dev_password` (the operator user; Google email `ed@timberbacklabs.com`). A *new* `*.weyland.lab` subdomain (e.g. `auth.weyland.lab`) needs an `/etc/hosts` line on the workstation until it's pointed at the wildcard LAN DNS — the browser resolves per-host, not via the wildcard.

## Web UIs (Traefik TLS, `*.weyland.lab` → mother `192.168.1.243`)

mkcert wildcard cert; resolve from rogueone (`/etc/hosts`) or via CoreDNS. **Most UIs are now Keycloak SSO** (see *Identity / SSO* above) — the old shared dev-password logins are retired for those apps.

| UI | URL |
|---|---|
| **Open WebUI** (voice/chat → Ollama + whisper) — **Keycloak SSO** (OIDC) | `https://chat.weyland.lab` |
| **LiteLLM** (model gateway admin UI / `/ui`) | `https://litellm.weyland.lab` |
| **Kiali** (Istio mesh graph + mTLS, **read-only**; traces from Tempo) — **Keycloak SSO** (forward-auth) | `https://kiali.weyland.lab` |
| Grafana (metrics + logs (Loki) + traces (Tempo) + alerts (Alertmanager, incl. **Loki-ruler log alerts**) — Explore/Drilldown) — **Keycloak SSO** (OIDC, CA-verified back-channel) | `https://grafana.weyland.lab` |
| **GlitchTip** (error tracking — Sentry-SDK-compatible) — **Keycloak SSO** (OIDC; via a DB-precreated social link — see [[glitchtip-allauth-sso-link]]) | `https://glitchtip.weyland.lab` |
| **OpenCost** (k8s cost allocation — custom on-prem pricing; LAN-only) | `https://opencost.weyland.lab` |
| **Woodpecker CI** (CI/CD — GitHub OAuth login; k8s backend; manual/cron triggers) | `https://woodpecker.weyland.lab` |
| **Argo CD** (GitOps CD — local admin; app-of-apps, 28 apps) | `https://argocd.weyland.lab` |
| **Platform Docs** (MkDocs Material — runbooks/architecture/concepts; browsable+searchable, Mermaid; B59, replaced Backstage TechDocs) | `https://docs.weyland.lab` |
| Dagster | `https://dagster.weyland.lab` |
| n8n | `https://n8n.weyland.lab` |
| Headlamp (k8s UI) | `https://headlamp.weyland.lab` |
| Filestash (MinIO browser — replaces the stripped community console) — **Keycloak SSO** (forward-auth; auto-connects to S3 behind the gate) | `https://files.weyland.lab` |
| ~~weyland IDP (Backstage, `idp.weyland.lab`)~~ — **RETIRED 2026-06-22 (B59)**; replaced by **Port.io** catalog + **`docs.weyland.lab`** | — |
| **Port.io** (IDP — SaaS; **launcher/catalog**, not status board) | `https://app.port.io` — EU org; **Launcher** dashboard (`endpoint` bp). Integrations: K8s, Istio, GitHub, Linear, Unleash (`feature_flag`), SonarQube (`code_quality`), Trivy+Semgrep (`security_scan`) |
| **MLflow** (experiment tracking + model registry; B10+B16) — **Keycloak SSO** (forward-auth) + **LAN NodePort** (`mlflow-lan`, unauth, `externalTrafficPolicy: Local`, iptables-pinned to rogueone — lets the external Ray worker log runs + register models; artifacts two-plane → direct to MinIO) | `https://mlflow.weyland.lab` · `http://192.168.1.243:30500` |
| **Container registry** (MinIO-backed OCI registry; remote-training capability) — **no auth** (LAN-only) | `https://registry.weyland.lab` — Docker API only (no web UI; browse `/v2/_catalog`). Blobs in MinIO `registry` bucket. See [runbooks/remote-training.md](runbooks/remote-training.md) |
| **Ray head** (persistent Ray cluster — dashboard + Jobs API; submit training / HP-sweep jobs) — **Keycloak SSO** (forward-auth) | `https://ray.weyland.lab` — GCS `mother:6379` (edge workers dial this); in-cluster Jobs API `ray-head.weyland.svc:8265`. rogueone joins as a native worker. See [runbooks/remote-training.md](runbooks/remote-training.md) |
| **Uptime Kuma** (live status board — own auth; **25 monitors**, Telegram paging; Port webhook retired) | `https://kuma.weyland.lab` |
| **Linear** (roadmap/task board — SaaS; Claude via MCP, Port ingests for status) | `https://linear.app/emangini` — projects: Weyland Lab / Stud.IO / Service Transformation |
| **Unleash** (feature flags; OSS self-hosted; → Port `feature_flag` webhook) — **Keycloak SSO** (forward-auth; own login behind = double) | `https://unleash.weyland.lab` — Python SDK for tool-server/Hermes; see [runbooks/unleash.md](runbooks/unleash.md) |
| **SonarQube** (code quality / static analysis; → Port `code_quality` webhook) — **Keycloak SSO** (forward-auth; own login behind = double; native OIDC possible later) | `https://sonarqube.weyland.lab` — meshed Postgres backend; on-demand scan Jobs (+ Trivy/Semgrep). See [runbooks/code-quality.md](runbooks/code-quality.md) |
| **Nessie** (data-mesh **B1.2** — Iceberg catalog + table versioning) — **Keycloak SSO** (forward-auth) | `https://nessie.weyland.lab` — UI + Iceberg REST `/iceberg` + API `/api/v2`. Programmatic: `nessie.data-mesh.svc.cluster.local:19120` (in-cluster, no gate) |
| **lakeFS** (data-mesh **B1.2** — file/dataset versioning) — **Keycloak SSO** (forward-auth; own access-key auth behind) | `https://lakefs.weyland.lab` — Programmatic: `lakefs.data-mesh.svc.cluster.local:8000` (in-cluster, no gate — forward-auth is browser-only, so CLI/pipelines use the svc directly) |

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

# Weyland Docs

**Weyland** is a home AI lab on a Minisforum MS-A2 (Proxmox): local LLM inference, multi-backend RAG,
speech-to-text, pipeline orchestration, an eval harness, observability, object storage, and AI agents — all
LAN-only. This `docs/` tree is the canonical, version-controlled source of truth (and the RAG corpus).

## Start here
- [arch.md](arch.md) — architecture: topology, components, validated flows, the *picture and the why*
- [data-mesh-guide.md](data-mesh-guide.md) — **the single source**: what every data store is *for*, a when-to-use-which decision matrix, and the workflow map
- [hosts.md](hosts.md) — host/container inventory (IPs, access, roles)
- [api.md](api.md) — live endpoint registry
- [schedules.md](schedules.md) — master timetable: all Dagster + DataHub cron jobs, TZ-normalized
- [definition-of-done.md](definition-of-done.md) — **the DoD**: the 8-pillar gate every body of work passes (docs · diagrams · demos · cleanup · close-out · operational-completeness · security-scan · cascading-changes)

## query/ — copy-paste queries, one file per store
[query/README.md](query/README.md) — real dataset-specific queries for every store (Trino/Iceberg, dbt marts,
GizmoSQL, ClickHouse, Cassandra, Cockroach, Mongo, MySQL, Timescale, Postgres, Neo4j, Qdrant/Weaviate, OpenSearch,
LanceDB, Redpanda, Feast). Which dataset lives where: [data-domain-storage-grid.csv](data-domain-storage-grid.csv).

## concepts/ — the *why*
- [llm-inference-cpu-vs-gpu.md](concepts/llm-inference-cpu-vs-gpu.md) — CPU=capacity vs GPU=speed
- [model-serving-hardware.md](concepts/model-serving-hardware.md) — MS-A2 sizing, model throughput, context windows
- [agent-platform-design.md](concepts/agent-platform-design.md) — Hermes agent design, MCP seam, A2A
- [data-schema.md](concepts/data-schema.md) — RAG (4 backends) + eval store schemas, ground-truth-validated

## runbooks/ — the *how* (per service)

- [agent-hermes.md](runbooks/agent-hermes.md) — Hermes agent (CT 104) setup, config, gotchas, **Kanban (B27)**
- [agentic-rag.md](runbooks/agentic-rag.md) — agentic RAG — the `weyland-agent` service (B70 Part 3)
- [aidlc-kb-ingest.md](runbooks/aidlc-kb-ingest.md) — AIDLC knowledge-base ingest (B37): MinIO source + brand scrub, on-demand Dagster job, Neo4j `:Entry` graph + GDS, NeoDash viz
- [aidlc-workflow.md](runbooks/aidlc-workflow.md) — AI-DLC v2 development workflow (B133) — `/aidlc` forwarding loop, stages, gates
- [argocd.md](runbooks/argocd.md) — Argo CD GitOps (B58) — app-of-apps, sync mechanism, why the refresh annotation is forbidden, selfHeal rollback traps
- [backups.md](runbooks/backups.md) — rogueone backups (B130) — restic → MinIO, `--files-from`/`forget`, Kuma dead-man's-switch
- [code-quality.md](runbooks/code-quality.md) — weekly 9-tool `code-scan-suite` + `sonar-scan` (B69/B89/B90): → Port `code_quality`/`security_scan`/`code_hotspot` + Code Health dashboard; vm.max_map_count, Port webhook + paste-mangling gotchas
- [code-review-stack.md](runbooks/code-review-stack.md) — the B106 adopted AI code-review set (7 tools, $0) — IDE + CI/PR lanes
- [coding-agents.md](runbooks/coding-agents.md) — coding agents (B15) — local-model / free-hosted coding TUIs
- [cube.md](runbooks/cube.md) — Cube semantic / metrics layer (B1.7 L6) — subPath + `MEASURE()` gotchas
- [data-mesh-secrets.md](runbooks/data-mesh-secrets.md) — data-mesh secret shapes, regeneration, and escrow
- [datahub.md](runbooks/datahub.md) — DataHub metadata catalog (B1.3): native recipe ingestion vs custom git-emit (`datahub_catalog_emit_job`), durable-secrets trap, GMS/token
- [datasets-hydration.md](runbooks/datasets-hydration.md) — datasets hydration — silver → Tier-2 stores (data-store-mageddon)
- [datasets-lake.md](runbooks/datasets-lake.md) — datasets lake — music + health domains, bronze → silver → gold (B72/B75)
- [dbt.md](runbooks/dbt.md) — dbt transform tier (B1.5): 7 tested marts via dbt-trino → Iceberg, artifact publish, DataHub cataloging, Trino-OOM guard
- [embedding-model-swap.md](runbooks/embedding-model-swap.md) — swapping the RAG embedding model — dimension migration
- [eval-harness.md](runbooks/eval-harness.md) — LLM eval pipeline, judge panel, leaderboard
- [flink.md](runbooks/flink.md) — Flink streaming tier (B83) — session cluster, 4 jobs, `jarURI` over http
- [gatekeeper.md](runbooks/gatekeeper.md) — OPA/Gatekeeper admission control (B1.6 L5 Slice B): no-latest/mem-limit/owner constraints, dryrun→deny, Policy Manager UI + Grafana dashboard
- [gizmosql.md](runbooks/gizmosql.md) — GizmoSQL — DuckDB over Arrow Flight SQL (B65 Tier-2 #2); DataGrip schema-browse limitation
- [glitchtip.md](runbooks/glitchtip.md) — GlitchTip error tracking (B51) — oversized-event drops, allauth SSO link
- [gpu-inference.md](runbooks/gpu-inference.md) — on-demand GPU inference (vLLM + SGLang) on rogueone — native-engine + KV-cache gotchas
- [guardrails.md](runbooks/guardrails.md) — the shared `weyland-guard` service (B14 + B70 Part 2)
- [jupyterhub.md](runbooks/jupyterhub.md) — JupyterHub notebook layer (B1.8 L8)
- [keda.md](runbooks/keda.md) — KEDA — **RETIRED 2026-08-22** (installed 62 days, never used); kept for its single-node replica + cert-timing gotchas
- [keycloak.md](runbooks/keycloak.md) — Keycloak IdP/SSO (B1.1): the `weyland` realm, native-OIDC vs forward-auth (auth-host mode, one redirect_uri, `/_oauth/logout`), mkcert CA back-channel, adding a gated subdomain
- [lan-dns.md](runbooks/lan-dns.md) — `weyland-lan-dns` — `*.weyland.lab` resolution, CoreDNS forward
- [langfuse.md](runbooks/langfuse.md) — Langfuse LLM observability (B103) — sessions, online evals, OOM/Redis gotchas
- [lightdash.md](runbooks/lightdash.md) — Lightdash dbt-native BI: trino-noauth proxy, PAT dbt project, metrics-as-code, S3, seed/content-as-code
- [likec4.md](runbooks/likec4.md) — LikeC4 architecture diagrams (B64) — one model → explorer + mkdocs
- [mcp-fleet.md](runbooks/mcp-fleet.md) — MCP server fleet (B17+B19 Phase 3) — 6 read-only servers + FastMCP compositor
- [mcp-gateway.md](runbooks/mcp-gateway.md) — `weyland-mcp-gateway` — mesh / fleet governance, Keycloak auth proxy
- [mlflow-gateway.md](runbooks/mlflow-gateway.md) — MLflow AI Gateway (B100 P4) — 17 endpoints + guardrails + budget
- [mlflow-training.md](runbooks/mlflow-training.md) — MLflow training — one model, two feature sources, three use cases
- [mlflow.md](runbooks/mlflow.md) — MLflow (B10+B16): experiment tracking + model registry, Postgres backend + MinIO artifacts, meshed, dev-password
- [model-gateway.md](runbooks/model-gateway.md) — LiteLLM hosted-model gateway (Gemini + OpenRouter) + model catalog
- [model-serving-ollama.md](runbooks/model-serving-ollama.md) — Ollama on rogueone (GPU, B79), models, tuning
- [musicbrainz-postgres.md](runbooks/musicbrainz-postgres.md) — MusicBrainz Postgres native mirror (Tier-2) — native `mbdump`, not mbslave
- [nessie.md](runbooks/nessie.md) — Nessie Iceberg REST catalog + table versioning (B1.2): Postgres version store + MinIO warehouse, native-Nessie catalog for Trino/dbt/Flink, branch/commit basics
- [node-capacity.md](runbooks/node-capacity.md) — mother RAM ceiling & the store-park discipline
- [node-memory-resilience.md](runbooks/node-memory-resilience.md) — swap-off + the memory-pressure survival test
- [observability-signals.md](runbooks/observability-signals.md) — the four signals — metrics · logs · traces · profiles
- [observability.md](runbooks/observability.md) — **full LGTM**: Prometheus + Grafana + Alertmanager (metrics/alerts), **Loki + Alloy** (logs), **Tempo** (traces, Jaeger retired), Proxmox pve-exporter; all in Grafana Explore/Drilldown
- [opencost.md](runbooks/opencost.md) — OpenCost cloud-cost (B55)
- [opentofu.md](runbooks/opentofu.md) — OpenTofu IaC (non-k8s lane) — state in MinIO, port-labs provider phantom
- [operator.md](runbooks/operator.md) — the `weyland-operator` service (B66) — LangGraph, Telegram read/act, 4-rail confirm
- [port-agent-easy-button.md](runbooks/port-agent-easy-button.md) — Port actions → cluster (port-agent + store-scaler); store sleep PARKED and why
- [port.md](runbooks/port.md) — Port.io IDP/catalog (B43/B58/B60): blueprints-as-code (tofu) vs MCP-managed entities, port-provider gotchas, "Port = see / Hermes = do" (action path → port-agent-easy-button)
- [pr-lifecycle.md](runbooks/pr-lifecycle.md) — the delivery-pipeline watchdogs (B131/B135): `pr-staleness-check` (open-PR age budgets) + `cron-freshness-check` (Woodpecker cron enabled/`next_exec` — not a k8s object, so no metric can see it) → Alertmanager → Telegram; per-cadence CronJob freshness rule + `absent()`; ConfigMap-as-tested-logic, Istio `/quitquitquit`
- [prompt-federation.md](runbooks/prompt-federation.md) — prompt federation (B103) — Bifrost SoT → Langfuse + MLflow sync
- [ranger.md](runbooks/ranger.md) — Apache Ranger data-plane authz for Trino (L5 Slice A) — native-ranger DEFAULT-DENY lockout
- [remote-training.md](runbooks/remote-training.md) — remote model training on rogueone — registry → Ray cluster → MLflow
- [secrets.md](runbooks/secrets.md) — SealedSecrets (B69) — the sealing mechanism, allow-list, restore, and the bricking key
- [service-mesh-istio.md](runbooks/service-mesh-istio.md) — Istio mesh (B8): install, sidecar injection, mTLS, Kiali (traces → Tempo), TCP-backend fix
- [ship-images.md](runbooks/ship-images.md) — the ship loop (B135): `scripts/ship-images.sh` detect → build → tag-bump PR → three-condition gated merge → scoped Argo sync → FR1.5 tag verify + SMOKE probe/availability gate; `argocd`/`woodpecker-cli`/`gh` prerequisites, gate-failure recovery, 62 bats
- [soda.md](runbooks/soda.md) — Soda data-quality scan for the marts (L5 Slice C)
- [storage-minio.md](runbooks/storage-minio.md) — MinIO object storage
- [streaming.md](runbooks/streaming.md) — streaming tier — Redpanda + Avro producer + Debezium CDC
- [superset.md](runbooks/superset.md) — Superset (B65 Tier-2 #3): ad-hoc BI/SQL over Trino, Keycloak OIDC
- [timescaledb.md](runbooks/timescaledb.md) — TimescaleDB time-series store (B65 Tier-2)
- [transcription-whisper.md](runbooks/transcription-whisper.md) — whisper.cpp STT (CT 103) + OpenAI shim
- [trino.md](runbooks/trino.md) — Trino federation query engine (native-Nessie iceberg + postgresql catalogs)
- [unleash.md](runbooks/unleash.md) — Unleash (B43, feature-mgmt): OSS feature flags, meshed Postgres, → Port `feature_flag` webhook; secret-paste + inotify gotchas
- [uptime-kuma.md](runbooks/uptime-kuma.md) — Uptime Kuma (B43): 16 monitors → Port.io webhook; LAN-CoreDNS + mkcert-CA gotchas, restore-into-empty
- [woodpecker.md](runbooks/woodpecker.md) — Woodpecker CI (B56/B57a/B57b) — mixed fleet by `backend` label, LAN NodePorts, the `nightly-images` cron

## units/ — task-scoped hardening/setup docs
`u6`–`u12` — credential hardening, HF cleanup, Headlamp token, mkcert/CoreDNS/Traefik (U9), SA scoping,
SSH identity, health endpoints. (Numbered to backlog units; see `aidlc-docs/`.)

## validation/
- [test-commands.md](validation/test-commands.md) — end-to-end validation commands

## diagrams/ — C4 + flows
**Architecture (C4)** is now interactive **LikeC4** (B64) — explore at [likec4.weyland.lab](https://likec4.weyland.lab)
or embedded: [context](diagrams/c4-context.md) · [node topology](diagrams/c4-container.md) ·
[components (mother, sliced into planes)](diagrams/c4-component-mother.md). Model: `architecture/weyland.likec4`.
Flows (Mermaid): [RAG query](diagrams/flow-rag-query.md),
[voice](diagrams/flow-voice-chat.md), [eval](diagrams/flow-eval.md), [agent MCP](diagrams/flow-agent-mcp.md), [MLflow](diagrams/flow-mlflow.md).

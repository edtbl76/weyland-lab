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
- [model-gateway.md](runbooks/model-gateway.md) — LiteLLM hosted-model gateway (Gemini + OpenRouter) + model catalog
- [model-serving-ollama.md](runbooks/model-serving-ollama.md) — Ollama on rogueone (GPU, B79), models, tuning
- [transcription-whisper.md](runbooks/transcription-whisper.md) — whisper.cpp STT (CT 103) + OpenAI shim
- [eval-harness.md](runbooks/eval-harness.md) — LLM eval pipeline, judge panel, leaderboard
- [observability.md](runbooks/observability.md) — **full LGTM**: Prometheus + Grafana + Alertmanager (metrics/alerts), **Loki + Alloy** (logs), **Tempo** (traces, Jaeger retired), Proxmox pve-exporter; all in Grafana Explore/Drilldown
- [service-mesh-istio.md](runbooks/service-mesh-istio.md) — Istio mesh (B8): install, sidecar injection, mTLS, Kiali (traces → Tempo), TCP-backend fix
- [keycloak.md](runbooks/keycloak.md) — Keycloak IdP/SSO (B1.1): the `weyland` realm, native-OIDC vs forward-auth (auth-host mode, one redirect_uri, `/_oauth/logout`), mkcert CA back-channel, adding a gated subdomain
- [datahub.md](runbooks/datahub.md) — DataHub metadata catalog (B1.3): native recipe ingestion vs custom git-emit (`datahub_catalog_emit_job`), durable-secrets trap, GMS/token
- [nessie.md](runbooks/nessie.md) — Nessie Iceberg REST catalog + table versioning (B1.2): Postgres version store + MinIO warehouse, native-Nessie catalog for Trino/dbt/Flink, branch/commit basics
- [gatekeeper.md](runbooks/gatekeeper.md) — OPA/Gatekeeper admission control (B1.6 L5 Slice B): no-latest/mem-limit/owner constraints, dryrun→deny, Policy Manager UI + Grafana dashboard
- [port.md](runbooks/port.md) — Port.io IDP/catalog (B43/B58/B60): blueprints-as-code (tofu) vs MCP-managed entities, port-provider gotchas, "Port = see / Hermes = do" (action path → port-agent-easy-button)
- [storage-minio.md](runbooks/storage-minio.md) — MinIO object storage
- [aidlc-kb-ingest.md](runbooks/aidlc-kb-ingest.md) — AIDLC knowledge-base ingest (B37): MinIO source + brand scrub, on-demand Dagster job, Neo4j `:Entry` graph + GDS, NeoDash viz
- [mlflow.md](runbooks/mlflow.md) — MLflow (B10+B16): experiment tracking + model registry, Postgres backend + MinIO artifacts, meshed, dev-password
- [uptime-kuma.md](runbooks/uptime-kuma.md) — Uptime Kuma (B43): 16 monitors → Port.io webhook; LAN-CoreDNS + mkcert-CA gotchas, restore-into-empty
- [unleash.md](runbooks/unleash.md) — Unleash (B43, feature-mgmt): OSS feature flags, meshed Postgres, → Port `feature_flag` webhook; secret-paste + inotify gotchas
- [code-quality.md](runbooks/code-quality.md) — SonarQube + Trivy + Semgrep (B43): on-demand scans → Port `code_quality`/`security_scan`; vm.max_map_count, Port webhook-wizard + paste-mangling gotchas
- [keda.md](runbooks/keda.md) — KEDA (autoscaling/run-mode engine for the data mesh): core + HTTP add-on, single-node replica gotcha
- [dbt.md](runbooks/dbt.md) — dbt transform tier (B1.5): 7 tested marts via dbt-trino → Iceberg, artifact publish, DataHub cataloging, Trino-OOM guard
- [lightdash.md](runbooks/lightdash.md) — Lightdash dbt-native BI: trino-noauth proxy, PAT dbt project, metrics-as-code, S3, seed/content-as-code
- [superset.md](runbooks/superset.md) — Superset (B65 Tier-2 #3): ad-hoc BI/SQL over Trino, Keycloak OIDC
- [trino.md](runbooks/trino.md) — Trino federation query engine (native-Nessie iceberg + postgresql catalogs)

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

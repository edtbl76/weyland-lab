# Weyland Docs

**Weyland** is a home AI lab on a Minisforum MS-A2 (Proxmox): local LLM inference, multi-backend RAG,
speech-to-text, pipeline orchestration, an eval harness, observability, object storage, and AI agents — all
LAN-only. This `docs/` tree is the canonical, version-controlled source of truth (and the RAG corpus).

## Start here
- [arch.md](arch.md) — architecture: topology, components, validated flows, the *picture and the why*
- [hosts.md](hosts.md) — host/container inventory (IPs, access, roles)
- [api.md](api.md) — live endpoint registry

## concepts/ — the *why*
- [llm-inference-cpu-vs-gpu.md](concepts/llm-inference-cpu-vs-gpu.md) — CPU=capacity vs GPU=speed
- [model-serving-hardware.md](concepts/model-serving-hardware.md) — MS-A2 sizing, model throughput, context windows
- [agent-platform-design.md](concepts/agent-platform-design.md) — Hermes/OpenClaw lanes, MCP seam, A2A
- [data-schema.md](concepts/data-schema.md) — RAG (4 backends) + eval store schemas, ground-truth-validated

## runbooks/ — the *how* (per service)
- [agent-hermes.md](runbooks/agent-hermes.md) — Hermes agent (CT 104) setup, config, gotchas, **Kanban (B27)**
- [model-gateway.md](runbooks/model-gateway.md) — LiteLLM hosted-model gateway (Gemini + OpenRouter) + model catalog
- [model-serving-ollama.md](runbooks/model-serving-ollama.md) — Ollama (CT 102), models, CPU tuning
- [transcription-whisper.md](runbooks/transcription-whisper.md) — whisper.cpp STT (CT 103) + OpenAI shim
- [eval-harness.md](runbooks/eval-harness.md) — LLM eval pipeline, judge panel, leaderboard
- [observability.md](runbooks/observability.md) — Prometheus + Grafana + Alertmanager
- [service-mesh-istio.md](runbooks/service-mesh-istio.md) — Istio mesh (B8): install, sidecar injection, mTLS, Kiali/Jaeger, TCP-backend fix
- [storage-minio.md](runbooks/storage-minio.md) — MinIO object storage
- [aidlc-kb-ingest.md](runbooks/aidlc-kb-ingest.md) — AIDLC knowledge-base ingest (B37): MinIO source + brand scrub, on-demand Dagster job, Neo4j `:Entry` graph + GDS, NeoDash viz
- [weyland-idp.md](runbooks/weyland-idp.md) — IDP / Backstage (B3): build-from-git (multi-stage), ConfigMap config, Postgres role, the mesh + guest-auth gotchas
- [mlflow.md](runbooks/mlflow.md) — MLflow (B10+B16): experiment tracking + model registry, Postgres backend + MinIO artifacts, meshed, dev-password
- [uptime-kuma.md](runbooks/uptime-kuma.md) — Uptime Kuma (B43): 16 monitors → Port.io webhook; LAN-CoreDNS + mkcert-CA gotchas, restore-into-empty
- [unleash.md](runbooks/unleash.md) — Unleash (B43, feature-mgmt): OSS feature flags, meshed Postgres, → Port `feature_flag` webhook; secret-paste + inotify gotchas
- [code-quality.md](runbooks/code-quality.md) — SonarQube + Trivy + Semgrep (B43): on-demand scans → Port `code_quality`/`security_scan`; vm.max_map_count, Port webhook-wizard + paste-mangling gotchas
- [keda.md](runbooks/keda.md) — KEDA (autoscaling/run-mode engine for the data mesh): core + HTTP add-on, single-node replica gotcha

## units/ — task-scoped hardening/setup docs
`u6`–`u12` — credential hardening, HF cleanup, Headlamp token, mkcert/CoreDNS/Traefik (U9), SA scoping,
SSH identity, health endpoints. (Numbered to backlog units; see `aidlc-docs/`.)

## validation/
- [test-commands.md](validation/test-commands.md) — end-to-end validation commands

## diagrams/ — C4 + flows
C4 [context](diagrams/c4-context.md) · [container](diagrams/c4-container.md) · components
([mother](diagrams/c4-component-mother.md), [hermes](diagrams/c4-component-hermes.md),
[ollama](diagrams/c4-component-ollama.md), [whisper](diagrams/c4-component-whisper.md),
[openclaw](diagrams/c4-component-openclaw.md), [rogueone](diagrams/c4-component-rogueone.md)).
Flows: [ingestion](diagrams/flow-ingestion.md), [RAG query](diagrams/flow-rag-query.md),
[voice](diagrams/flow-voice-chat.md), [eval](diagrams/flow-eval.md), [agent MCP](diagrams/flow-agent-mcp.md), [MLflow](diagrams/flow-mlflow.md), [IDP self-sync](diagrams/flow-idp-sync.md).

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
- [agent-hermes.md](runbooks/agent-hermes.md) — Hermes agent (CT 104) setup, config, gotchas
- [model-serving-ollama.md](runbooks/model-serving-ollama.md) — Ollama (CT 102), models, CPU tuning
- [transcription-whisper.md](runbooks/transcription-whisper.md) — whisper.cpp STT (CT 103) + OpenAI shim
- [eval-harness.md](runbooks/eval-harness.md) — LLM eval pipeline, judge panel, leaderboard
- [observability.md](runbooks/observability.md) — Prometheus + Grafana + Alertmanager
- [storage-minio.md](runbooks/storage-minio.md) — MinIO object storage

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
[voice](diagrams/flow-voice-chat.md), [eval](diagrams/flow-eval.md), [agent MCP](diagrams/flow-agent-mcp.md).

# Weyland — API & Endpoint Inventory

Live registry of **every API/endpoint in the lab**. Manual precursor to **B12** (aggregated
OpenAPI portal). Keep this updated as endpoints are added/changed (see [[feedback-keep-api-hosts-updated]]).

Hosts & access users: [hosts.md](hosts.md). `mother` = 192.168.1.243, CTs by IP (or the new
`*.weyland.lab` names once CoreDNS picks them up).

`✅ OpenAI /v1` = speaks the OpenAI API shape (the endpoints a future portal/agent can drop into).

## Model serving (inference / STT)

| Service | Host | Endpoint | OpenAI? | Notes |
|---|---|---|---|---|
| **Ollama** (LLM) | ollama CT 102 | `http://ollama.weyland.lab:11434/v1` (`192.168.1.244`) | ✅ | 6 models; `num_thread 8`. See [b7-ollama-runbook.md](b7-ollama-runbook.md). |
| **whisper shim** (STT) | whisper CT 103 | `http://whisper.weyland.lab:9000/v1/audio/transcriptions` (`192.168.1.246`) | ✅ | OpenAI-compatible adapter → whisper.cpp. See [b11-whisper-runbook.md](b11-whisper-runbook.md). |
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

## Object storage (MinIO)

| Service | Endpoint | Notes |
|---|---|---|
| MinIO S3 API | `https://s3.weyland.lab` | S3-compatible; mc on rogueone. See [b6-minio-storage.md](b6-minio-storage.md). |
| MinIO console | `https://minio.weyland.lab` | community console stripped — use Filestash instead |

## Infrastructure

| Service | Endpoint | Notes |
|---|---|---|
| CoreDNS (LAN resolver) | `mother:53` | authoritative for `weyland.lab`; forwards else to 1.1.1.1/9.9.9.9 |

---
**Conventions:** standalone CTs (ollama/whisper) use their reserved IPs or `*.weyland.lab` names
(added to CoreDNS). k3s services use `mother:<NodePort>` or `*.weyland.lab` (Traefik). Internal-only
services use cluster DNS (`*.weyland.svc`).

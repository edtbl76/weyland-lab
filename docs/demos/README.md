# Weyland — Demos & Workflow Coverage

Every end-to-end workflow in the lab must be **(1)** diagrammed as a **sequence diagram**, **(2)** demonstrated
here with a **complete UI *and* CLI walkthrough**, and **(3)** paired with a **cleanup/teardown** if it creates
data. This is the platform's Definition of Done (see the `completion-criteria` memory). This file is the tracked
worklist — a demo is not done until all three columns are ✅.

Legend: ✅ done · ⬜ missing · 🟡 exists but stale/partial · — not applicable

## Coverage matrix

| # | Workflow | Sequence diagram | Demo (UI + CLI) | Creates data → cleanup |
|---|---|---|---|---|
| **Data mesh / pipelines** | | | | |
| 1 | RAG streaming indexer (B-RAG-STREAM: produce → 5 store consumers) | ✅ `flow-rag-stream` | ✅ `rag-stream.md` | ✅ probe teardown (full run writes the LIVE index — destructive) |
| 2 | RAG query / retrieval | ✅ `flow-rag-query` | ✅ `rag-query.md` | — read-only |
| 3 | RAG ingestion (in-process) | 🟡 `flow-ingestion` — **SUPERSEDED by #1** (`flow-rag-stream`) | — | — |
| 4 | Datasets → lakehouse | ✅ (seq added) | ✅ `datasets-lakehouse.md` | ✅ idempotent overwrites |
| 5 | Streaming (Redpanda + Avro) | ✅ (seq added) | ✅ `streaming.md` | ✅ topics |
| 6 | CDC (Debezium → topics) | ✅ (seq added) | ✅ `cdc.md` | ✅ CDC topics |
| 7 | Flink streaming tier | ✅ `flow-flink` | ✅ `flink.md` (all 4 jobs validated 2026-07-15) | ✅ Iceberg analytics.* |
| 8 | LanceDB sync | ✅ (seq added) | ✅ `lancedb.md` | ✅ Lance tables |
| 9 | Feast feature store | ✅ (seq added) | ✅ `feast.md` | read-only serving |
| 10 | Semantic consumption (Cube/MetricFlow) | ✅ (seq added) | ✅ `semantic-consumption.md` | — read-only |
| 11 | dbt build → marts | ✅ | ✅ `dbt.md` | ✅ iceberg.dbt.* |
| 12 | Store wake/sleep scaler | ✅ `flow-store-scaler` | ✅ `store-scaler.md` | — replicas only |
| 13 | DataHub catalog emit | ✅ (authored) | ✅ `catalog-emit.md` | ✅ DataHub entities |
| 14 | Pipeline trigger (Dagster) | ✅ `flow-pipeline-trigger` | ✅ `pipeline-trigger.md` | — |
| **ML / eval** | | | | |
| 15 | Eval harness | ✅ `flow-eval` | ✅ `eval.md` | ✅ eval runs |
| 16 | Eval scoring (LLM-judge) | ✅ `flow-eval-scoring` | ✅ `eval-scoring.md` | ✅ scores |
| 17 | Model catalog | ✅ `flow-model-catalog` | ✅ `model-catalog.md` | ✅ Postgres/DataHub |
| 18 | MLflow tracking | ✅ `flow-mlflow` | ✅ `mlflow.md` | ✅ experiments |
| 19 | Remote training (Ray → MLflow) | ✅ (authored) | ✅ `remote-training.md` | ✅ artifacts/models |
| **Agent / serving** | | | | |
| 22 | Voice chat (Open WebUI + whisper) | ✅ `flow-voice-chat` | ✅ `voice-chat.md` | — |
| 23 | Model gateway / backend dispatch | ✅ `flow-model-gateway` | ✅ `model-gateway.md` | — |
| 24 | Guardrails / redaction | ✅ `flow-guardrails` | ✅ `guardrails.md` | — |
| **Platform / ops** | | | | |
| 25 | Deploy (GitOps / Argo) | ✅ (authored) | ✅ `deploy.md` | — |
| 26 | Ingress + TLS | ✅ `flow-ingress-tls` | ✅ `ingress-tls.md` | — |
| 27 | Mesh mTLS | ✅ `flow-mesh-mtls` | ✅ `mesh-mtls.md` | — |
| 28 | Tracing (Tempo) | ✅ `flow-tracing` | ✅ `tracing.md` | — |
| 29 | Alerting | ✅ `flow-alerting` | ✅ `alerting.md` | ✅ test rule apply+delete |
| 30 | Health status (Uptime Kuma) | ✅ (authored) | ✅ `health-status.md` | — |
| 31 | Roadmap sync (Linear) | ✅ (authored) | ✅ `roadmap-sync.md` | ✅ Linear issues |
| 32 | Architecture diagrams (LikeC4, B64) | — (the C4 views ARE the diagram) | ✅ `likec4.md` | — read-only |

## Outstanding (before any row is truly 100%)

- **Flink demo (#7) is DONE** — all 4 jobs (RTA / CDC / health / PyFlink) validated end-to-end 2026-07-15
  (B83): declarative `FlinkSessionJob`s + History Server, results in Iceberg `analytics.*` and Kafka. Row flipped
  to ✅.
- **`flow-ingestion` is SUPERSEDED** — it diagrams the retired in-process RAG chain; the live path is
  `flow-rag-stream` / `rag-stream.md` (#1). Marked SUPERSEDED here rather than deleted for history.
- **`TODO: verify` markers to resolve** (honest unknowns left by the generators, none fabricated):
  eval FK column · `valve.sh` path · guardrail dotted-validator env var · datahub emit-token secret name ·
  `model_catalog` columns · Ollama model tags · MLflow 3.14 delete CLI · `datasets_lib._catalog` signature ·
  `psql` on the trino image · in-pod `dagster asset materialize -m` invocation · `cdc_demo` columns + mb-pg
  workload name · pgvector/neo4j consumer-group deletion via `redpanda-0` · `/context/search` body ·
  roadmap field mapping.
- **Doc discrepancy to reconcile:** Uptime Kuma monitor count — `runbooks/uptime-kuma.md` says 16,
  `hosts.md` says 25.

All 28 demos + all sequence diagrams are written; the items above are the residual verifications, not gaps in
coverage.

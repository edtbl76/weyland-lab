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
| 15 | Eval harness | ✅ `flow-eval` | ✅ `eval.md` | ✅ eval runs (validated live runs 7-10, 2026-07-21 — golden set + depth sweep) |
| 16 | Eval scoring (LLM-judge) | ✅ `flow-eval-scoring` | ✅ `eval-scoring.md` | ✅ scores |
| 37 | **Model-Eval Leaderboard** data product (B84 P1 — DataHub product + Data Contract + Superset + Port) | ✅ (seq in eval flows) | ✅ `model-eval-product.md` (validated 2026-07-24) | — read-only (catalog metadata + Superset defs) |
| 38 | **Eval lanes — when to use each** (B84 P2 — panel vs `mlflow.evaluate` vs Promptfoo) | — decision ref | ✅ `eval-lanes.md` (validated 2026-07-25) | ✅ Promptfoo runs (promptfoo.weyland.lab) |
| 39 | **MLflow AI Gateway** (B100 P4 — 17 endpoints + guardrails + budget, one self-healing script) | — (scripts are the flow) | ✅ `mlflow-gateway.md` (validated 2026-07-25) | ✅ endpoints/scorers/guardrails/budget (gateway DB) |
| 40 | **Coding agents** (B15 — opencode/Cline/Pi/Codex on free/`$0` drivers + ChatGPT sub) | — (client config) | ✅ `coding-agents.md` (validated 2026-07-27) | ✅ writes reverse.py + test_reverse.py, pytest green |
| 17 | Model catalog | ✅ `flow-model-catalog` | ✅ `model-catalog.md` | ✅ Postgres/DataHub |
| 18 | MLflow tracking | ✅ `flow-mlflow` | ✅ `mlflow.md` | ✅ experiments |
| 36 | **MLflow GenAI** (B100 — Traces + Prompt Registry, hot-swap) | ✅ (seq in demo) | ✅ `mlflow-genai.md` (validated 2026-07-24) | ✅ traces + prompt versions (history) |
| 19 | Remote training (Ray → MLflow) | ✅ (authored) | ✅ `remote-training.md` | ✅ artifacts/models |
| **Agent / serving** | | | | |
| 21 | Agentic RAG (`weyland-agent`, B70) | ✅ `flow-agentic-rag` | ✅ `agentic-rag.md` (validated live 2026-07-23) | — read-only (traces/verdicts) |
| 22 | Voice chat (Open WebUI + whisper) | ✅ `flow-voice-chat` | ✅ `voice-chat.md` | — |
| 23 | Model gateway / backend dispatch | ✅ `flow-model-gateway` | ✅ `model-gateway.md` | — |
| 24 | Guardrails platform (B70 Scan + **B115 Classify · Structure · Dialog**) | ✅ `flow-guardrails` · `flow-eval-scoring` · `flow-nemo-dialog` (+ Concepts page) | ✅ `guardrails.md` (Scan + Classify 1B/8B + Structure guarded/reasked + Dialog off-topic/jailbreak, validated 2026-08-03) | ✅ read-only (demo-actor rows + eval spans) |
| 34 | Operator brain bake-off (B66 — Claude vs local, tool-use) | — (test harness) | ✅ `brain-bakeoff.md` — tool-selection + full-loop all-models run 2026-07-23 (verdict: brain = `gpt-oss:20b`) | — read-only |
| 35 | **Operator agent** (`weyland-operator`, B66 — Telegram → read/act, confirm-step) | ✅ `flow-operator` · `flow-operator-brain` | ✅ `operator.md` (validated live 2026-07-24; local-primary brain + failover validated live 2026-08-04 — `brain="local"` @ 15.2s) | 🟡 fire path launches a real ingestion run; session rows |
| 36 | **Operator incident sweep** (`weyland-operator`, B45 — firing ALERTS → enrich → Telegram digest; enrich-only, off the critical path) | ✅ `flow-incident-sweep` | 🟡 `incident-sweep.md` (authored 2026-08-04; the sweep **ran live** and caught the 12-day backup outage — demo-doc steps RUN-pending) | ✅ read-only (dedup rows + Telegram) |
| 37 | **GPU inference bench** (B111 — three engines: Ollama simple · vLLM throughput · SGLang prefix-cache) | — (benches, not a multi-participant flow) | ✅ `gpu-inference.md` (validated 2026-07-31: vLLM ~15× tok/s + SGLang ~6.2× TTFT, extreme-detail explainers) | — frees VRAM (`bench.sh stop`), no data |
| **Platform / ops** | | | | |
| 25 | Deploy (GitOps / Argo) | ✅ (authored) | ✅ `deploy.md` | — |
| 26 | Ingress + TLS | ✅ `flow-ingress-tls` | ✅ `ingress-tls.md` | — |
| 27 | Mesh mTLS | ✅ `flow-mesh-mtls` | ✅ `mesh-mtls.md` | — |
| 28 | Tracing (Tempo) | ✅ `flow-tracing` | ✅ `tracing.md` | — |
| 29 | Alerting | ✅ `flow-alerting` | ✅ `alerting.md` | ✅ test rule apply+delete; + Dagster watchdog synthetic alert → Telegram verified (B94) |
| 30 | Health status (Uptime Kuma) | ✅ (authored) | ✅ `health-status.md` | — |
| 31 | Roadmap sync (Linear) | ✅ (authored) | ✅ `roadmap-sync.md` | ✅ Linear issues |
| 32 | Architecture diagrams (LikeC4, B64) | — (the C4 views ARE the diagram) | ✅ `likec4.md` | — read-only |
| 33 | Code quality / security scan (scan-suite → Port) | ✅ `flow-code-quality` | ✅ `code-quality-e2e.md` | ✅ smoke Jobs (deleted); Port upserts idempotent |
| 42 | **STUD.io CI on the weyland Woodpecker farm** (B57b — mixed fleet: local-backend agents on rogueone; CLI via `:30980` NodePort) | ✅ `flow-woodpecker-studio-ci` | ✅ `woodpecker-studio-ci.md` (RUN — pipelines #5–#10 green 2026-08-17; 3 workflows main·plugin-scanner·roadie after the throwaway `pilot` smoke test was retired) | ✅ drops `masterdb_test_ci{,_0..3}` (prod `masterdb` never touched) |
| 43 | **weyland image CI → CD** (B57a — build weyland images on the farm → registry → tag-bump PR → Argo; buildkitd daemon; nightly 01:00 cron) | ✅ `flow-weyland-image-ci` | ✅ `weyland-image-ci.md` (RUN — #8/#9 → PR #9 → `store-scaler` rolled to `git-ec59b430`, 2026-08-18) | — read-mostly; registry tags = deploy history; cache PVC reproducible |
| 44 | **CI reliability signal** (B63 — Woodpecker run outcome → Port `ci_pipeline` → `weyland_ci_reliability` dashboard; both backends, both outcomes) | ✅ `flow-ci-reliability-signal` | ✅ `ci-reliability-signal.md` (RUN — weyland-lab #12 success · stud.io #14 failure · stud.io #15 success, 2026-08-19; eyes-on dashboard) | ✅ creates `ci_pipeline` entities (real runs = history; throwaway test rows deleted via Port API) |
| 45 | **STUD.io code-review stack** (B118 — the B106 stack on the public `edtbl76/stud.io` repo; parity + Port components cover both repos) | ✅ `flow-studio-code-review` | ✅ `studio-code-review.md` (RUN — verified on stud.io PR #121: DeepSource×7 · CodeScene 78184 · Sourcery · CodeRabbit · Qodo, 2026-08-19) | — read-only (inspects PR checks + Port entities) |
| **End-to-end walkthroughs** (cross-system) — all 🟡 authored, pending a live validation run | | | | |
| E1 | RAG (doc change → index → retrieve → eval) | ✅ `flow-e2e-rag` | 🟡 `rag-e2e.md` | ✅ eval run/scores (per leg) |
| E2 | Soda data-quality → DataHub Assertions | ✅ `flow-e2e-soda` | 🟡 `soda-dq.md` | — read-only + idempotent upserts |
| E3 | Great Expectations profiling → DataHub Assertions + Data Docs (B77b) | ✅ `flow-great-expectations` | ✅ `great-expectations.md` | — on-demand `ge_validate_job`; read-only profiling |
| E3 | Ranger column masking (masked vs unmasked) | ✅ `flow-e2e-ranger` | 🟡 `ranger-masking.md` | — read-only |
| E4 | Governance (lineage + DQ + masking on one dataset) | ✅ `flow-e2e-governance` | 🟡 `governance-e2e.md` | — non-destructive |
| E5 | DataHub maturity: contracts mesh-wide · siblings merge · stats-wide (B80) | ✅ inline seq | ✅ `datahub-maturity.md` | — read-only emit; per-twin contracts |
| E5 | ML lifecycle (silver → Feast → Ray → MLflow → serve/consume) | ✅ `flow-e2e-ml` | 🟡 `ml-lifecycle-e2e.md` | ✅ MLflow version/artifact (per leg) |
| E6 | Lakehouse (land → lakeFS → Iceberg → dbt marts → BI + Tier-2) | ✅ `flow-e2e-lakehouse` | 🟡 `lakehouse-e2e.md` | ✅ idempotent overwrites |
| E7 | Streaming + CDC (produce/Debezium → Redpanda → Flink → Iceberg → Trino) | ✅ `flow-e2e-streaming-cdc` | 🟡 `streaming-cdc-e2e.md` | ✅ topics + Iceberg `analytics.*` |
| E8 | Deploy (git push → Argo sync → rollout → verify) | ✅ `flow-e2e-deploy` | 🟡 `deploy-e2e.md` | — GitOps reconcile |
| E9 | Observability (app → Prom/Loki/Tempo → Grafana → Alertmanager → Telegram) | ✅ `flow-e2e-observability` | 🟡 `observability-e2e.md` | ✅ test alert apply+delete |
| E10 | SSO (browser → forward-auth → Keycloak → app, one login) | ✅ `flow-e2e-sso` | 🟡 `sso-e2e.md` | — read-only |
| E11 | Agent (Telegram → Hermes → LiteLLM/Ollama → MCP → tool-server → reply) | ✅ `flow-e2e-agent` | 🟡 `agent-e2e.md` | — read-only |
| E12 | Store wake/sleep (Port action → port-agent → store-scaler → k8s scale) | ✅ `flow-e2e-store-scale` | 🟡 `store-scale-e2e.md` | — replicas only |
| B82 | Application taxonomy (registry → DataHub Applications + Port components, one SoT) | ✅ `flow-application-taxonomy` | ✅ `application-taxonomy.md` (RUN — `(29,4157)` + eyes-on) | — read-only |

> **E-rows are 🟡 authored — pending live validation run.** Commands are real (pulled from the component
> demos/runbooks, no placeholders, host-labeled), but per the demos DoD a demo is not ✅ until executed
> straight through against live infra. Each E-file carries a "> Pending live end-to-end validation run" note.

## Outstanding (before any row is truly 100%)

- **Flink demo (#7) is DONE** — all 4 jobs (RTA / CDC / health / PyFlink) validated end-to-end 2026-07-15
  (B83): declarative `FlinkSessionJob`s + History Server, results in Iceberg `analytics.*` and Kafka. Row flipped
  to ✅.
- **`flow-ingestion` is SUPERSEDED** — it diagrams the retired in-process RAG chain; the live path is
  `flow-rag-stream` / `rag-stream.md` (#1). Marked SUPERSEDED here rather than deleted for history.
- **`TODO: verify` markers to resolve** (honest unknowns left by the generators, none fabricated):
  eval FK column · `valve.sh` path · datahub emit-token secret name ·
  `model_catalog` columns · Ollama model tags · MLflow 3.14 delete CLI · `datasets_lib._catalog` signature ·
  `psql` on the trino image · in-pod `dagster asset materialize -m` invocation · `cdc_demo` columns + mb-pg
  workload name · pgvector/neo4j consumer-group deletion via `redpanda-0` · `/context/search` body ·
  roadmap field mapping.
- **Uptime Kuma monitor count RECONCILED** — the live SQLite count is **37** (2026-07-17); fixed in both
  `runbooks/uptime-kuma.md` and `hosts.md` (were 16 / 25).

All 28 component demos + all sequence diagrams are written; the items above are the residual verifications, not
gaps in coverage.

**Cross-system coverage:** 12 end-to-end walkthroughs (E1–E12) thread the component demos into full workflows
across every plane — RAG · Soda DQ · Ranger masking · governance · ML lifecycle · lakehouse · streaming/CDC ·
deploy · observability · SSO · agent · store wake/sleep — each with its own `flow-e2e-*` sequence diagram. All 12
are **🟡 authored — pending a live end-to-end validation run** (the last mile: run each straight through to flip
🟡 → ✅, which also resolves the `TODO: verify` markers). Prev/next chain pointers link the component demos
(`rag-stream`↔`rag-query`; `streaming`/`cdc`→`flink`; `datasets-lakehouse`→`dbt`→`semantic-consumption`).

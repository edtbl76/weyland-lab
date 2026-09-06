# Weyland — Demos & Workflow Coverage

Every end-to-end workflow in the lab must be **(1)** diagrammed as a **sequence diagram**, **(2)** demonstrated
here with a **complete UI *and* CLI walkthrough**, and **(3)** paired with a **cleanup/teardown** if it creates
data. This is the platform's Definition of Done (see the `completion-criteria` memory). This file is the tracked
worklist — a demo is not done until all three columns say DONE.

Legend: **DONE** · **MISSING** · **PARTIAL** (exists but stale) · — not applicable

## Coverage matrix

| # | Workflow | Sequence diagram | Demo (UI + CLI) | Creates data → cleanup |
|---|---|---|---|---|
| **Data mesh / pipelines** | | | | |
| 1 | RAG streaming indexer (B-RAG-STREAM: produce → 5 store consumers) | DONE `flow-rag-stream` | DONE `rag-stream.md` | DONE probe teardown (full run writes the LIVE index — destructive) |
| 2 | RAG query / retrieval | DONE `flow-rag-query` | DONE `rag-query.md` | — read-only |
| 3 | RAG ingestion (in-process) | PARTIAL `flow-ingestion` — **SUPERSEDED by #1** (`flow-rag-stream`) | — | — |
| 4 | Datasets → lakehouse | DONE (seq added) | DONE `datasets-lakehouse.md` | DONE idempotent overwrites |
| 5 | Streaming (Redpanda + Avro) | DONE (seq added) | DONE `streaming.md` | DONE topics |
| 6 | CDC (Debezium → topics) | DONE (seq added) | DONE `cdc.md` | DONE CDC topics |
| 7 | Flink streaming tier | DONE `flow-flink` | DONE `flink.md` (all 4 jobs validated 2026-07-15) | DONE Iceberg analytics.* |
| 8 | LanceDB sync | DONE (seq added) | DONE `lancedb.md` | DONE Lance tables |
| 9 | Feast feature store | DONE (seq added) | DONE `feast.md` | read-only serving |
| 10 | Semantic consumption (Cube/MetricFlow) | DONE (seq added) | DONE `semantic-consumption.md` | — read-only |
| 11 | dbt build → marts | DONE | DONE `dbt.md` | DONE iceberg.dbt.* |
| 12 | Store wake/sleep scaler | DONE `flow-store-scaler` | DONE `store-scaler.md` | — replicas only |
| 13 | DataHub catalog emit | DONE (authored) | DONE `catalog-emit.md` | DONE DataHub entities |
| 14 | Pipeline trigger (Dagster) | DONE `flow-pipeline-trigger` | DONE `pipeline-trigger.md` | — |
| **ML / eval** | | | | |
| 15 | Eval harness | DONE `flow-eval` | DONE `eval.md` | DONE eval runs (validated live runs 7-10, 2026-07-21 — golden set + depth sweep) |
| 16 | Eval scoring (LLM-judge) | DONE `flow-eval-scoring` | DONE `eval-scoring.md` | DONE scores |
| 37 | **Model-Eval Leaderboard** data product (B84 P1 — DataHub product + Data Contract + Superset + Port) | DONE (seq in eval flows) | DONE `model-eval-product.md` (validated 2026-07-24) | — read-only (catalog metadata + Superset defs) |
| 38 | **Eval lanes — when to use each** (B84 P2 — panel vs `mlflow.evaluate` vs Promptfoo) | — decision ref | DONE `eval-lanes.md` (validated 2026-07-25) | DONE Promptfoo runs (promptfoo.weyland.lab) |
| 39 | **MLflow AI Gateway** (B100 P4 — 17 endpoints + guardrails + budget, one self-healing script) | — (scripts are the flow) | DONE `mlflow-gateway.md` (validated 2026-07-25) | DONE endpoints/scorers/guardrails/budget (gateway DB) |
| 40 | **Coding agents** (B15 — opencode/Cline/Pi/Codex on free/`$0` drivers + ChatGPT sub) | — (client config) | DONE `coding-agents.md` (validated 2026-07-27) | DONE writes reverse.py + test_reverse.py, pytest green |
| 17 | Model catalog | DONE `flow-model-catalog` | DONE `model-catalog.md` | DONE Postgres/DataHub |
| 18 | MLflow tracking | DONE `flow-mlflow` | DONE `mlflow.md` | DONE experiments |
| 36 | **MLflow GenAI** (B100 — Traces + Prompt Registry, hot-swap) | DONE (seq in demo) | DONE `mlflow-genai.md` (validated 2026-07-24) | DONE traces + prompt versions (history) |
| 19 | Remote training (Ray → MLflow) | DONE (authored) | DONE `remote-training.md` | DONE artifacts/models |
| **Agent / serving** | | | | |
| 21 | Agentic RAG (`weyland-agent`, B70) | DONE `flow-agentic-rag` | DONE `agentic-rag.md` (validated live 2026-07-23) | — read-only (traces/verdicts) |
| 22 | Voice chat (Open WebUI + whisper) | DONE `flow-voice-chat` | DONE `voice-chat.md` | — |
| 23 | Model gateway / backend dispatch | DONE `flow-model-gateway` | DONE `model-gateway.md` | — |
| 24 | Guardrails platform (B70 Scan + **B115 Classify · Structure · Dialog**) | DONE `flow-guardrails` · `flow-eval-scoring` · `flow-nemo-dialog` (+ Concepts page) | DONE `guardrails.md` (Scan + Classify 1B/8B + Structure guarded/reasked + Dialog off-topic/jailbreak, validated 2026-08-03) | DONE read-only (demo-actor rows + eval spans) |
| 34 | Operator brain bake-off (B66 — Claude vs local, tool-use) | — (test harness) | DONE `brain-bakeoff.md` — tool-selection + full-loop all-models run 2026-07-23 (verdict: brain = `gpt-oss:20b`) | — read-only |
| 35 | **Operator agent** (`weyland-operator`, B66 — Telegram → read/act, confirm-step) | DONE `flow-operator` · `flow-operator-brain` | DONE `operator.md` (validated live 2026-07-24; local-primary brain + failover validated live 2026-08-04 — `brain="local"` @ 15.2s) | PARTIAL fire path launches a real ingestion run; session rows |
| 36 | **Operator incident sweep** (`weyland-operator`, B45 — firing ALERTS → enrich → Telegram digest; enrich-only, off the critical path) | DONE `flow-incident-sweep` | PARTIAL `incident-sweep.md` (authored 2026-08-04; the sweep **ran live** and caught the 12-day backup outage — demo-doc steps RUN-pending) | DONE read-only (dedup rows + Telegram) |
| 37 | **GPU inference bench** (B111 — three engines: Ollama simple · vLLM throughput · SGLang prefix-cache) | — (benches, not a multi-participant flow) | DONE `gpu-inference.md` (validated 2026-07-31: vLLM ~15× tok/s + SGLang ~6.2× TTFT, extreme-detail explainers) | — frees VRAM (`bench.sh stop`), no data |
| **Platform / ops** | | | | |
| 25 | Deploy (GitOps / Argo) | DONE (authored) | DONE `deploy.md` | — |
| 26 | Ingress + TLS | DONE `flow-ingress-tls` | DONE `ingress-tls.md` | — |
| 27 | Mesh mTLS | DONE `flow-mesh-mtls` | DONE `mesh-mtls.md` | — |
| 28 | Tracing (Tempo) | DONE `flow-tracing` | DONE `tracing.md` | — |
| 29 | Alerting | DONE `flow-alerting` | DONE `alerting.md` | DONE test rule apply+delete; + Dagster watchdog synthetic alert → Telegram verified (B94) |
| 30 | Health status (Uptime Kuma) | DONE (authored) | DONE `health-status.md` | — |
| 31 | Roadmap sync (Linear) | DONE (authored) | DONE `roadmap-sync.md` | DONE Linear issues |
| 32 | Architecture diagrams (LikeC4, B64) | — (the C4 views ARE the diagram) | DONE `likec4.md` | — read-only |
| 33 | Code quality / security scan (scan-suite → Port) | DONE `flow-code-quality` | DONE `code-quality-e2e.md` | DONE smoke Jobs (deleted); Port upserts idempotent |
| 42 | **STUD.io CI on the weyland Woodpecker farm** (B57b — mixed fleet: local-backend agents on rogueone; CLI via `:30980` NodePort) | DONE `flow-woodpecker-studio-ci` | DONE `woodpecker-studio-ci.md` (RUN — pipelines #5–#10 green 2026-08-17; 3 workflows main·plugin-scanner·roadie after the throwaway `pilot` smoke test was retired) | DONE drops `masterdb_test_ci{,_0..3}` (prod `masterdb` never touched) |
| 43 | **weyland image CI → CD** (B57a — build weyland images on the farm → registry → tag-bump PR → Argo; buildkitd daemon; nightly 01:00 cron) | DONE `flow-weyland-image-ci` | DONE `weyland-image-ci.md` (RUN — #8/#9 → PR #9 → `store-scaler` rolled to `git-ec59b430`, 2026-08-18) | — read-mostly; registry tags = deploy history; cache PVC reproducible |
| 44 | **CI reliability signal** (B63 — Woodpecker run outcome → Port `ci_pipeline` → `weyland_ci_reliability` dashboard; both backends, both outcomes) | DONE `flow-ci-reliability-signal` | DONE `ci-reliability-signal.md` (RUN — weyland-lab #12 success · stud.io #14 failure · stud.io #15 success, 2026-08-19; eyes-on dashboard) | DONE creates `ci_pipeline` entities (real runs = history; throwaway test rows deleted via Port API) |
| 45 | **STUD.io code-review stack** (B118 — the B106 stack on the public `edtbl76/stud.io` repo; parity + Port components cover both repos) | DONE `flow-studio-code-review` | DONE `studio-code-review.md` (RUN — verified on stud.io PR #121: DeepSource×7 · CodeScene 78184 · Sourcery · CodeRabbit · Qodo, 2026-08-19) | — read-only (inspects PR checks + Port entities) |
| 46 | **rogueone backup + restore** (B130 — encrypted restic → MinIO; Port dashboard + Kuma dead-man's-switch; the 3-domain local-only-gap model) | DONE `flow-backup` | DONE `backup-restore.md` (RUN — snapshot `d1e2bc7e` 652 MiB; mkcert/`.claude`-memory/STUD.io-`.env` restored byte-identical, 2026-08-20) | DONE restore → `/tmp` scratch (removed); snapshots pruned 7d/4w/6m |
| 47 | **AI-DLC v2 workflow** (B133 — `/aidlc` forwarding loop; Method retired, knowledge-repos decoupled) | DONE `flow-aidlc-workflow` | PARTIAL `aidlc-workflow.md` — **Part A engine validation RUN 2026-08-20** (doctor 47/0, 0 graph cycles, 33 stages topo-ordered, `scope-table --check` clean, Bedrock-strip + absolute-bun both 0, 511 KB skills / 116 prompts regression green, retired-generator guard exits 1); **Part B gated run NOT YET EXECUTED — validation tracked in B87** alongside E1–E12. Uses a disposable `/tmp` fixture under **`bugfix`** scope (must skip discovery: `poc`/`feature`/`mvp`/`enterprise` pull in `intent-capture`, which asks for a business case a fixture cannot answer — that stalled the first attempt). Fixture defect reproduction verified 2026-08-20. | DONE Part A read-only (`--dry`/`--check`); Part B fixture lives in `/tmp` + one intent record → both torn down, verified via `status` + `doctor` |
| 48 | **Ship loop + delivery watchdogs** (B135/B131 — gated merge of the CI tag-bump PR → scoped Argo sync → FR1.5 tag verify + SMOKE probe gate; `pr-staleness-check` + `cron-freshness-check` → Alertmanager → Telegram) | DONE `flow-ship-loop` | PARTIAL `ship-images.md` — **full ship RUN 2026-08-22** (pipeline #24 → PR #35 → three affected applications → 5 workloads on `git-36c4d3e0`), gate-refusal RUN (PR #34 aborted at FR2.1), nothing-to-ship RUN, cron-triggered build RUN 2026-08-23 (pipeline #25, 82s), pr-staleness RUN ×3 (4 real alerts → Telegram), 62 bats green. **NOT yet run (deferred to EMA-77):** the `SMOKE` gate live, `cron-freshness-check`'s first scheduled firing, and a cron-produced bump PR — all three need a day where an image build context actually changes · **DORA emit added 2026-08-27 (EMA-172)** — every ship records a Port `deployment` entity; lead time measured from the SOURCE COMMIT, not the PR (PR created→merged is 24s on this loop and would read 0.0 forever) | DONE ad-hoc watchdog Jobs deleted; synthetic alerts auto-resolve (5m); a real ship is reversed by **git revert**, not `argocd app rollback` (selfHeal trap) |
| 49 | **Port IaC coverage** (B137 — Port schema under OpenTofu + the guard that asks what `tofu plan` structurally cannot: what is LIVE that the code does not describe) | DONE `flow-port-iac-coverage` | DONE `port-iac-coverage.md` (RUN 2026-08-25 — 51/21/30 blueprints · 8/8 scorecards · 4/4 integrations, 0 missing; negative case RUN with the scorecards hidden → exit 1 naming all 8; `k8s_workload` CronJob entities 0 → 10; 18 bats green, each mutation-verified) | DONE step 3 writes a throwaway `.tf` copy to `/tmp` (removed); all other steps read-only |
| 50 | **Port PR entity reconciliation** (B144 — the reaper the Ocean integration does not have: it fetches only OPEN PRs, so a closed PR's entity survives forever claiming `status: open` and inflates two DORA scorecards) | DONE `flow-port-pr-reconcile` | DONE `port-pr-reconcile.md` (RUN 2026-08-25 — dry run flagged weyland-lab#36 alone out of 8; live run reaped it; acceptance **port=7 github=7 MATCH**; 19 bats green, TDD Red→Green) | DONE **DESTRUCTIVE** — deletes catalog entities the integration will NOT recreate; entity backed up to /tmp before the live run and a restore command is in the demo |
| 51 | **Sealed placeholder + the guard** (B147 — a credential that was perfectly restorable and authenticated to nothing; `port-creds` held YOUR_ID/YOUR_SECRET for 63 days and silently killed the B62 AI-Dev Usage pipeline) | DONE `flow-secret-placeholders` | DONE `secret-placeholders.md` (RUN 2026-08-25 — guard 56/56 clean after the fix, negative case RUN, stored value 401→**200**, `ai_session` 37→**62** with 25 createdBy the integration; 20 bats green, TDD Red→Green) | DONE steps 1/2/4/6/7 read-only; step 3 writes a /tmp fixture; step 5 upserts real pipeline output (idempotent, nothing to undo) |
| 52 | **ServiceMonitor coverage + the Trino blind spot** (B148 — a ServiceMonitor that existed, was committed, was Argo-applied and was `kubectl get`-able for **59 days** while producing zero metrics; the `trino` Service carried no `metadata.labels`, and a ServiceMonitor matches SERVICES by their own labels, not by the `spec.selector` that matches pods) | DONE `flow-servicemonitor-coverage` | DONE `servicemonitor-coverage.md` (RUN 2026-08-26 — guard 32/32 after the fix, negative case RUN with exit **1** vs **2** distinguished, `trino_*` 0→**4228** series, endpoint contract observed (`Password not allowed for insecure authentication` → empty password is REQUIRED); 30 bats green, TDD Red→Green→live Red→live Green) | DONE steps 1/2/4/5/6 read-only; step 3 writes two /tmp fixtures; step 7 creates an ad-hoc Job that rotates out via `successfulJobsHistoryLimit` |
| 53 | **DoD Pillar 5 reconciliation** (the one pillar with no checker — every other has `check-mermaid`/`check-doc-counts`/`check-cron-freshness-budgets`/bats/eyes-on, so here the tick WAS the work and recorded intent rather than outcome; the B148 close-out claimed "Linear EMA-207" with no Linear call ever made) | OK `flow-linear-sync` | OK `linear-sync.md` (RUN 2026-08-26 — live `OK - 26 refs reconciled`, BOTH negative cases RUN with exit **1**, missing-key path RUN with exit **2**; found EMA-207 + EMA-199 closed-in-fact-but-open-in-Linear and 3 project-less open issues; 23 bats green, TDD Red→Green) | OK steps 1/2/6 read-only; steps 3-5 write /tmp fixtures, removed in teardown; the guard has no write path and the API key needs read scope only |
| 54 | **Graphify code-cascade analysis** (EMA-191 — DoD Pillar 8's trigger-cascade table is all INFRASTRUCTURE surfaces (service, endpoint, timer, image, repo) and none of them ask about CODE cascade; that is why a byte-identical duplicate of `guardrails/verdict.py` could sit between two services with `Hook` values acting as URL paths and no pillar would raise it) | OK `flow-graphify` | OK `graphify.md` (RUN 2026-08-26 — build 1872 files → **13,051 nodes / 21,163 edges in ~16s, no network**; `affected GuardrailPipeline` exact file:line, correctly excluding the definition site; shell refusal RUN (12 real sourcers vs raw graphify's misleading `No affected nodes found`); ambiguity aid RUN, naming the two duplicated copies; `verify` proven to FAIL with exit **1**; 32 bats green, TDD Red→Green) | OK repo untouched — venv/copy/graph live under `~/.local/share/weyland/graphify/`; no skill registered, `~/.claude/CLAUDE.md` unmodified, no git hook; teardown is one `find -delete` |
| 55 | **Finance data domain** (B113 — FRED macro + SEC EDGAR XBRL + filings-text RAG on `datasets_lib`) | DONE `flow-finance-ingestion` (flowchart + sequence; Phase-2 + Phase-3 flowcharts) | DONE `finance-domain.md` (RUN end-to-end: **P1** FRED 13 series/40,930 obs → Timescale+ClickHouse+`mart_macro_indicators`; **P2** EDGAR 20,741 facts/49 dims → ClickHouse+Cockroach+MySQL+Mongo+`mart_company_financials`+Neo4j (49 SIC / 1,144 filings); **P3** 42 filers → **8,851** 10-K chunks → Qdrant/Weaviate/LanceDB **8,851 each** (dim 384) + `63_rag_sec_filings.ipynb`; **P4** full daily OHLCV (yfinance; stooq now PoW-walled) → Timescale hypertable + ClickHouse + Cassandra + `mart_price_daily`; **P5** ML lane — `mart_price_features` → Feast point-in-time → `finance-trainer` → **2 MLflow models** (volatility regressor R²≈0.43 + vol-regime classifier acc≈0.64); BI Lightdash/Superset/Cube; DataHub Finance domain + 4 products; Soda green; **B113 COMPLETE**) | DONE idempotent — static snapshots reproducible from FRED/SEC/yfinance; stores truncate-and-reload; notebook + models read-only |
| 56 | **DataHub catalog-coverage guard** (B158 follow-up A — the 4th coverage guard, first on the DATA estate not infra: nothing failed when a mesh dataset existed in Trino but was never emitted to DataHub; the audit even caught the `data-mesh-map` product tile drifting from the emit's real `_PRODUCTS` by hand) | DONE `flow-datahub-coverage` (gap-it-catches flowchart · guard sequence · fail-closed decision) | DONE `datahub-coverage.md` (+ runbook `observability.md#datahub-catalog-coverage`) — RUN 2026-09-05: live **111/111** catalogued, 0 drift; two live-only bugs found + fixed (Trino `nextUri` in-cluster host; `set -o pipefail`+`grep -q` SIGPIPE turning a real match into no-match, invisible to the small bats fixtures); negative cases RUN — exit **1** drift, exit **2** fail-closed; 12 bats green, TDD Red→Green→live | DONE read-only (one Trino query + a paged GMS read + a set diff); nightly `datahub-coverage` CronJob |
| 57 | **ODCS data contracts + conformance** (B157 — the mesh had contract SUBSTANCE (dbt tests · Soda · DataHub DataContracts) but no single declarative standard and nothing that FAILED on a malformed/incomplete contract) | DONE `flow-odcs-contracts` (substance→contract→mirror · three gates cheap→live) | DONE `odcs-contracts.md` — RUN 2026-09-05: all 3 domains contracted, **10** `*.odcs.yaml` (finance hand-authored, music/health via `gen_odcs_contract.py` from Trino+Soda+dbt); structural gate **10 bats**; live `--check-schema` all 10 conform + a bogus column caught (exit 1); products-without-contracts pytest 10/10; **dbt `contract: enforced` CONFIRMED by live `dbt build`s across all three domains** — finance 4 marts (PASS=16) + music/health 6 product marts (PASS=32), ERROR=0 | DONE contracts are git artifacts; generator + gates read-only; the confirming `dbt build` rebuilt the 4 finance marts (idempotent, same as the weekly job) |
| **End-to-end walkthroughs** (cross-system) — all PARTIAL authored, pending a live validation run | | | | |
| E1 | RAG (doc change → index → retrieve → eval) | DONE `flow-e2e-rag` | PARTIAL `rag-e2e.md` | DONE eval run/scores (per leg) |
| E2 | Soda data-quality → DataHub Assertions | DONE `flow-e2e-soda` | PARTIAL `soda-dq.md` | — read-only + idempotent upserts |
| E3 | Great Expectations profiling → DataHub Assertions + Data Docs (B77b) | DONE `flow-great-expectations` | DONE `great-expectations.md` | — on-demand `ge_validate_job`; read-only profiling |
| E3 | Ranger column masking (masked vs unmasked) | DONE `flow-e2e-ranger` | PARTIAL `ranger-masking.md` | — read-only |
| E4 | Governance (lineage + DQ + masking on one dataset) | DONE `flow-e2e-governance` | PARTIAL `governance-e2e.md` | — non-destructive |
| E5 | DataHub maturity: contracts mesh-wide · siblings merge · stats-wide (B80) | DONE inline seq | DONE `datahub-maturity.md` | — read-only emit; per-twin contracts |
| E5 | ML lifecycle (silver → Feast → Ray → MLflow → serve/consume) | DONE `flow-e2e-ml` | PARTIAL `ml-lifecycle-e2e.md` | DONE MLflow version/artifact (per leg) |
| E6 | Lakehouse (land → lakeFS → Iceberg → dbt marts → BI + Tier-2) | DONE `flow-e2e-lakehouse` | PARTIAL `lakehouse-e2e.md` | DONE idempotent overwrites |
| E7 | Streaming + CDC (produce/Debezium → Redpanda → Flink → Iceberg → Trino) | DONE `flow-e2e-streaming-cdc` | PARTIAL `streaming-cdc-e2e.md` | DONE topics + Iceberg `analytics.*` |
| E8 | Deploy (git push → Argo sync → rollout → verify) | DONE `flow-e2e-deploy` | PARTIAL `deploy-e2e.md` | — GitOps reconcile |
| E9 | Observability (app → Prom/Loki/Tempo → Grafana → Alertmanager → Telegram) | DONE `flow-e2e-observability` | PARTIAL `observability-e2e.md` | DONE test alert apply+delete |
| E10 | SSO (browser → forward-auth → Keycloak → app, one login) | DONE `flow-e2e-sso` | PARTIAL `sso-e2e.md` | — read-only |
| E11 | Agent (Telegram → Hermes → LiteLLM/Ollama → MCP → tool-server → reply) | DONE `flow-e2e-agent` | PARTIAL `agent-e2e.md` | — read-only |
| E12 | Store wake/sleep (Port action → port-agent → store-scaler → k8s scale) | DONE `flow-e2e-store-scale` | PARTIAL `store-scale-e2e.md` | — replicas only |
| B82 | Application taxonomy (registry → DataHub Applications + Port components, one SoT) | DONE `flow-application-taxonomy` | DONE `application-taxonomy.md` (RUN — `(29,4157)` + eyes-on) | — read-only |
| B88 | Per-language build lanes + supply chain (9 test langs → 3 scan lanes → SBOM/sign/attest → Gatekeeper dryrun) | DONE `flow-build-lanes` | DONE `build-lanes-supply-chain.md` (RUN — SBOM 96/16, audit 0, 310 bats, all CLI verified) | — read-only |
| B88-B | **CI/CD hardening** (Track B gaps #1–#6 — coverage ratchet · integration black-boxes · per-build vuln + Δ vs deployed · post-deploy transactions (Ready≠works) · Unleash deploy kill-switch · toolchain caching) | DONE `flow-cicd-hardening` (6 sequence diagrams) | DONE `cicd-hardening.md` (RUN — ratchet 80→71.5 exit 1 baseline held · guard 5/5 + datahub MAE/MCE Stable live · vuln 327[12C/73H] Δ:no-new (CI #47) · txn_tool_server TXN_OK · flag ON→ALLOW/OFF→HELD/ON→ALLOW live) | — #1 writes /tmp/base.tsv (rm); #2 `--rm` pods; #5 toggles flag then restores ON |
| B81 | **JupyterHub notebook library** (B1.8 follow-on — 25 numbered notebooks + `datasets_lake` seed spanning the whole data/ml/ai stack; git-sync distribution, singleuser mesh-join; U16 Weaviate satisfied by nb 31) | [flow-jupyter-notebook-library.md](../diagrams/flow-jupyter-notebook-library.md) | DONE `jupyter-notebook-library.md` (RUN + eyes-on 2026-09-02 — 26/26 headless PASS IN-POD via Keycloak-spawned singleuser pod; UI spawn/git-sync/mesh-join UAT; nb 51 model-load graceful-note by design) | DONE mostly read-only; 10/11/33 self-clean their scratch; nb 81 leaves an intentional `bravo-v3` CDC row; pods cull to zero |

> **E-rows are PARTIAL authored — pending live validation run.** Commands are real (pulled from the component
> demos/runbooks, no placeholders, host-labeled), but per the demos DoD a demo is not DONE until executed
> straight through against live infra. Each E-file carries a "> Pending live end-to-end validation run" note.

## Outstanding (before any row is truly 100%)

- **Flink demo (#7) is DONE** — all 4 jobs (RTA / CDC / health / PyFlink) validated end-to-end 2026-07-15
 (B83): declarative `FlinkSessionJob`s + History Server, results in Iceberg `analytics.*` and Kafka. Row flipped
 to DONE.
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
are **PARTIAL authored — pending a live end-to-end validation run** (the last mile: run each straight through to flip
PARTIAL → DONE, which also resolves the `TODO: verify` markers). Prev/next chain pointers link the component demos
(`rag-stream`↔`rag-query`; `streaming`/`cdc`→`flink`; `datasets-lakehouse`→`dbt`→`semantic-consumption`).

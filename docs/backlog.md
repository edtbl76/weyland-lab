# Weyland Forward Roadmap — re-prioritized 2026-06-14

Re-ordered per RE-grounded audit (aidlc-docs/inception/backlog-reprioritization.md). Immediate directives: B29 (connect Claude Code to weyland MCP) and B25 (docs IA + git RAG ingestion). Three priority groups: Real Purpose / Extras+Optimization / Hardware-Gated.

> **Agent topology — decided 2026-06-14: OpenClaw is DEPRIORITIZED entirely.** Hermes is the primary and
> effectively only active agent. OpenClaw was a "play with a powerful tool" lab experiment — fragile, painful
> to operate (gateway-container only), currently degraded (MCP not surfacing to its brain, no command owner,
> claude-cli auth expiring, memory search off, plaintext secrets), and nothing depends on it. Its unique edge
> (Claude brain, skill/channel breadth) is eroded by B26 — Hermes gained strong **free hosted brains**
> (Gemini / OpenRouter via the LiteLLM gateway); the Hermes-Claude path itself was *declined* (ToS/cost).
> **Rehab = B28, much later.** Read all
> "both agents" references below as **Hermes-now / OpenClaw-when-B28-lands**. See [[openclaw-deprioritized]].

## DONE (repo-verified)
- **B5** — Prometheus + Grafana observability — ✅ **DONE (2026-06-13)**. Phase 1: stack up,
  Grafana on TLS (grafana.weyland.lab), cluster/node dashboards. **Phase 2a: native
  Alertmanager → Telegram** (Weyland Alerts bot `@weyland_alerts_bot`; token in Secret; validated
  end-to-end; chosen native over n8n — fewer deps in the alert path). **Phase 2b: app ServiceMonitors**
  — Qdrant / Weaviate / APISIX / CoreDNS all scraped (`serviceMonitorSelectorNilUsesHelmValues:false`;
  k8s/monitoring/servicemonitors.yaml), 4 targets UP. APISIX needed `export_addr.ip:0.0.0.0` (defaulted
  to loopback). **Traefik descoped** (k3s-managed load-bearing ingress — blast radius > value in a lab).
  Runbook docs/runbooks/observability.md.
- **U12** — tool-server health/status endpoints — ✅ **DONE (2026-06-09)**: /ready, /status, /pgvector/health, probes, v0.2.0 → units-iter1.md
- **B6** — MinIO object storage — ✅ **DONE (2026-06-11)**: 8TB USB → MinIO on mother VM (raw passthrough), Filestash UI (files.weyland.lab), mc on rogueone. Runbook docs/runbooks/storage-minio.md.
- **B7** — larger models on weyland via **Ollama (CPU)** — ✅ **DONE (2026-06-11)**: CT 102 live (Ollama, OpenAI `/v1` at 192.168.1.244:11434); `num_thread 8` fix (~160× → ~25 tok/s on 30B-A3B MoE); 6 models benchmarked; docs split → b7-model-serving-hardware / b7-llm-inference-cpu-vs-gpu / b7-ollama-runbook. eGPU → Tentative. **Fully closed 2026-06-12:** IP DHCP-reserved; tool-server wired (v0.3.0 RAG `/context/ask` + per-request model select, `/models`, `/ollama/health`), validated mother + rogueone; deploy/test in docs/validation/test-commands.md.
- **B11** — Whisper STT (speech→text) — ✅ **SERVICE DONE (2026-06-12)**: whisper.cpp on CT 103 (CPU, `large-v3`); native `/inference` + OpenAI shim `/v1/audio/transcriptions` @ 192.168.1.246:9000; validated rogueone + openclaw VM. Runbook docs/runbooks/transcription-whisper.md.
- **B13** — Open WebUI — ✅ **DONE (2026-06-12)**: browser voice/chat at https://chat.weyland.lab; chat ← Ollama (6 models auto-listed), voice-in ← whisper shim (validated end-to-end — mic → `POST /v1/audio/transcriptions` on CT 103). mother/k3s, weyland ns, Traefik TLS; manifests k8s/open-webui/.
- **B4** — LLM eval/observability — ✅ **DONE (2026-06-13)**: full single-path eval pipeline (testset → run-matrix → **3-judge panel** scoring → `eval_leaderboard`) over RAG × 6 models, reusing Postgres/Dagster/Ollama; Ragas rejected (broken+heavy); tool-server **v0.4.0** `/evals/{run,score,runs,leaderboard}`. **gpt-oss:20b the defensible pick**; single-judge proven noisy. Runbook docs/runbooks/eval-harness.md.
- **B2** — Hermes agent platform (OpenClaw sibling) — **v1 LIVE 2026-06-14**: Hermes CT 104 on `qwen3-coder:30b` (MoE); read-only **system-view MCP server** (4 tools: status/context_search/context_ask/list_models) built into the tool-server via `fastapi-mcp` `mount_http()`, registered in Hermes, **validated end-to-end** (agent → MCP → live backend health). **Telegram gateway front door LIVE 2026-06-14** (allowlisted DM → agent reply). Runbook docs/runbooks/agent-hermes.md · design docs/concepts/agent-platform-design.md.
- **B23** — Break out `arch.md` component diagrams — ✅ **DONE (2026-06-14)**: created `docs/diagrams/` with full C4 hierarchy (L1 context, L2 container, L3 component × 6: mother/hermes/ollama/whisper/openclaw/rogueone) + 5 Mermaid sequence flow diagrams = 13 files total. arch.md rewritten as narrative + embedded C4Context + links to all diagrams. Note: Mermaid C4 renderer is basic — consider Structurizr at B25 IA overhaul time.
- **B29** — Connect Claude Code → weyland system-view MCP — ✅ **DONE (2026-06-14)**: registered via `claude mcp add weyland --transport http http://192.168.1.243:30080/mcp`; validated live — `status` tool returned all 4 backends ok + 6 Ollama models. Claude Code is now a first-class MCP consumer alongside Hermes.

---

## Priority — work top-down

### Immediate
1. **B31** — Codebase audit / restructure (`nodes/`) — **AUDIT DONE 2026-06-15.** Tree is clean: retired 2 dead bootstrap scripts; flagged 1 committed secret (gitignored — needs untrack+rotate, your task); OpenClaw scripts → B28, watcher → B25b. No restructure needed. See detail below.
2. **B25** — Docs + codebase RAG ingestion — ✅ **DONE 2026-06-15.** B25a (docs restructure) + B25b (Dagster git-pull of `docs/` + `nodes/`, dual chunking) live & validated end-to-end: 40 markdown + 76 code docs in the RAG (was 1), code retrievable via the MCP from Claude Code. Watcher retired. **Orphan reconciliation** (prune sources no longer in the repo across all 4 backends) + **eval-corpus markdown filter** added & validated 2026-06-15 (the old `obsidian` orphan auto-pruned on the next run). See detail below.

### Platform Foundation
4. **B24** — Evaluate nerdctl — ✅ **EVALUATED 2026-06-15 → DECLINE.** Keep docker + `save|import` as a deliberate build↔runtime anti-corruption layer; nerdctl's only real win (build into k3s's live image store) violates it, and keeping docker alongside would only add daemons. See detail below.
5. **B14** — Guardrails + Hermes read+act — ✅ **DONE 2026-06-15.** Both halves shipped: guardrail I/O layer (injection/toxicity/grounding on `/context/*`) + read+act (act-tools on `/mcp-act`, `act` hook audits to `guardrail_verdicts` with the `actor` seam), all `mode=shadow` (record-only — the right default for a single-user LAN lab). Shadow plumbing is complete; the enforcement *promotions* are carved out as their own downstream items, not B14 scope: grounding `shadow→flag/block` calibration + act policy gate → **B35**, PII bake → **B34**, gateway auth/actor injection → **B17+B19**. See detail below.
6. **B26** — Hosted-model gateway (LiteLLM) + model catalog — ✅ **DONE 2026-06-17** (reframed from "Hermes Claude brain"; Claude path declined — ToS gray area). LiteLLM on mother fronts all Gemini+OpenRouter; Dagster `model_catalog` (6h). See detail below.
7. **B27** — Hermes Kanban (self-management + roadmap co-pilot) — ✅ **DONE 2026-06-17.** Native SQLite kanban; planning on Gemini-free via the gateway (`kanban_decomposer`/`triage_specifier` pinned), workers local; `weyland-roadmap` board mirrors this backlog one-way (`roadmap-sync.py`, 6h cron). See detail below + [runbooks/agent-hermes.md](runbooks/agent-hermes.md#kanban--self-management--roadmap-co-pilot-b27-live-2026-06-17).
8. **B8** — Istio service mesh — **DECIDED BUILD-NOW 2026-06-17** (all four drivers: mTLS/observability/traffic-mgmt/learning). Design: `aidlc-docs/construction/b8-istio-design.md` — Approach 1 (sidecar, contained tool-server slice, bookinfo warm-up); step-0 mother-headroom gate → pivot to ambient if tight; **slice 1 = PERMISSIVE everywhere** (tool-server serves external NodePort MCP; backends serve un-meshed Dagster) — STRICT enforcement deferred to slice 2 (mesh Dagster); Traefik stays the ingress. See detail below.
- **B37** — **Ingest the AIDLC knowledge repositories into the (Graph) RAG** — ✅ **DONE 2026-06-19.** ~510 brand-neutral entries ingested from MinIO into all 4 backends (`aidlc-kb/` namespace, KB-scoped hash-gate + prune); RAG answers cite KB files (DDD ← `domain-driven-design.md`/`context-mapping.md`). **Phase 2 graph live:** 510 `:Entry` nodes, 2311 `RELATED_TO` + `SURFACES_AT`/`TAGGED`/`IN_VERTICAL` edges from frontmatter (no LLM). On-demand `weyland_aidlc_kb_job`; runbook [runbooks/aidlc-kb-ingest.md](runbooks/aidlc-kb-ingest.md). Fuzzy LLM extraction → **B38**. See detail below.
9. **B3** — IDP / Backstage — **✅ RETIRED 2026-06-22 (B59)** (was a learning project — slices A+B). Fully torn down once Port reached catalog parity: app (`k8s/weyland-idp/`) + 12 `backstage_plugin_*` DBs + `weyland_idp` Postgres role + MinIO `techdocs` bucket + the `weyland_techdocs_job` Dagster asset, all removed. Replaced by **Port.io** catalog (codified in `tofu/port/`) + **`docs.weyland.lab`** (standalone MkDocs Material). B40 (Mermaid) + B42 (scaffolder) now moot. See B59.

### Data & Automation
10. **B10+B16** — MLflow (experiment tracking + model registry) — ✅ **DONE 2026-06-19.** Live at `mlflow.weyland.lab` (dev-password): Postgres backend store + MinIO `mlflow` artifact bucket (proxied `--serve-artifacts`), meshed, smoke-tested end-to-end (run + metric + artifact). `k8s/mlflow/`. See detail below.
11. **B1** — **Data mesh — the Iteration-2 platform build.** FULL design locked in `aidlc-docs/data-mesh-design.md` (~30 techs across 8 layers; single-node **run-mode tiered** — always-on foundation vs KEDA/operator on-demand). The **3 data products are the *output*** — they ride on the platform below, they are NOT the build. Sequenced into dependency-ordered slices (storage→catalog/gov→query→transform→consumption); **Keycloak pulled to the front** (lab-wide SSO, not mesh-specific — pays off immediately):
    - **B1.1 — Identity / SSO (Keycloak)** — **✅ DONE 2026-06-24.** Keycloak (`keycloak.weyland.lab`, `weyland` realm, k8s + meshed Postgres) = lab IdP; realm + clients in `tofu/keycloak/`. **6 apps cut over:** OIDC native (Grafana — hardened/CA-verified · GlitchTip — via a DB-precreated allauth social link · Open WebUI) + **forward-auth** via `traefik-forward-auth` (`auth.weyland.lab`, MLflow/Kiali/filestash; cookie domain `weyland.lab` = one login + single logout `/_oauth/logout`). **Woodpecker left on GitHub-forge auth** (no generic OIDC); MinIO console dead → storage SSO = forward-auth on **filestash**, S3 API stays on access keys. **Gating EXTENDED 2026-06-25 → every browser UI** (forward-auth added to Unleash/SonarQube/Uptime-Kuma/Dagster/n8n/Woodpecker/Argo CD/Headlamp/OpenCost/LiteLLM/docs-site/APISIX-dash + Nessie/lakeFS; own-login apps = double-login). Data/API plane (S3 API, NodePort data backends, APISIX gateway) stays API-auth'd — can't browser-SSO. Gotchas (all in [[keycloak-sso-b1.1]]): Python apps need a system+mkcert CA bundle for the OIDC back-channel; cross-ns Traefik middleware blocked (local copy per ns); in-cluster DNS via `coredns-custom`; new `*.weyland.lab` subdomains need `/etc/hosts`. **Google brokering SHELVED 2026-06-24 — blocked by LAN-only:** Google OAuth rejects a `.lab` redirect URI (needs a public TLD), and the only fix is a public-domain overlay of the whole IdP (re-host Keycloak + repoint all 6 clients, since issuer = hostname) — not worth it for a solo lab; password login suffices. See [[keycloak-sso-b1.1]], [[lan-no-github-webhooks]]. (Keycloak chosen over Okta — LAN can't depend on cloud auth.)
    - **B1.2 — L1 Storage foundation** — **✅ DONE 2026-06-25.** **Nessie** (`nessie.weyland.lab` — Iceberg catalog + table versioning; Postgres `nessie` DB, warehouse = MinIO `warehouse` bucket, Iceberg REST at `/iceberg`) + **lakeFS** (`lakefs.weyland.lab` — file/dataset versioning; Postgres `lakefs` DB, blockstore = MinIO `lakefs` bucket) in a new **`data-mesh`** namespace, both meshed to STRICT Postgres. `k8s/data-mesh/`, Argo app `data-mesh`. Iceberg = the table format they enable (no service; lands with Trino/Dagster writes at B1.4+). Traps (all in [[data-mesh-b1.2-storage]]): Nessie STATIC S3 creds = a flat URN ref + a HYPHEN-FREE secret name (env vars can't express a hyphen); forward-auth gate is browser-only → CLI/API clients (lakectl, later Dagster/Trino) hit the in-cluster service directly, not the gated ingress.
    - **B1.3 — L4 Catalog** — **DataHub** (always-on centerpiece: ES + internal Kafka + GMS + frontend) + **ODCS** data contracts. Dropped Amundsen/OpenDataMeshPlatform. **ES = first-class shared service** (decided 2026-06-24): stand up DataHub's required Elasticsearch as its *own* exposed catalog service, not DataHub-internal — one ES the lab can reuse for search/log experiments (no second ES on the single node).
    - **B1.4 — L2 Query / Federation** — **Trino** (federated SQL over Iceberg/Postgres) + **DuckDB** (embedded) + **TimescaleDB** (Postgres extension, hot time-series; no InfluxDB).
    - **B1.5 — L3 Transform** — **dbt Core** + **SQLMesh** + **dlt** (EL) + **Debezium** (CDC). The **Kafka (Strimzi) + Flink streaming tier stays ON-DEMAND** (per-job via KEDA + Flink Operator) — deferrable; real work is Dagster batch (existing). No Airflow/Airbyte.
    - **B1.6 — L5 Governance** — **OpenLineage** (Dagster→DataHub, drop Marquez) + **Ranger** (data-plane authz: Trino column/row masking) + **OPA** (control-plane Rego) + **Soda** DQ (dbt-expectations already in-pipeline from B1.5).
    - **B1.7 — L6+L7 Consumption** — **Cube** (semantic layer) + **dbt Semantic Layer/MetricFlow** + **Lightdash** + **Superset** (BI, both on-demand). No Metabase.
    - **B1.8 — L8 Data Science** — **JupyterHub** (KubeSpawner) + **Feast** (feature store, reuses Postgres) + **Ray** (KubeRay), on-demand. **Deferred.** **Scope add 2026-06-27:** first deliverable = a **polars notebook that queries all 4 datasets-lake silver formats** (Parquet · Arrow · Avro · Lance) from lakeFS **in-cluster** — JupyterHub is polars' proper home (native lakeFS/MinIO access → no port-forward, venv, or TLS-cert friction). Seed = `nodes/mother/lab/weyland-platform/scripts/query_datasets_formats.py` (the rogueone harness). DuckDB+pyarrow exploration lands here too once that store exists.
    - **B1.9 — The 3 data products** (ride on B1.1–B1.8): (1) model-eval (judge-panel leaderboard); (2) store-inventory → recast as lineage/observability; (3) model-tuning feed → fine-tuning (Feast→MLflow).

### Maturity / Hardening / Polish
12. **B15** — Local-model coding agents (opencode / Cline CLI) — hardening agentic capabilities; autonomous unattended coding tasks; full value when Hermes delegates via mesh. See detail below.
13. **B17+B19** — "Mesh": A2A evaluation + MCP gateway — MERGED; same inflection point (fleet is real, govern it). Triggered after B14+B26+B27 + B3 stable + OpenClaw decision made. See detail below.
14. **U18** — ✅ **DONE 2026-06-17 (as KEY RETIREMENT, not lockdown).** B25b removed the SFTP ingestion that U18 was hardening → the `weyland-lab` key had zero consumers (repo grep clean). Retired it instead: deleted rogueone `authorized_keys` line + the orphaned `weyland-lab-ssh-key` k8s Secret. See detail below.
15. **B20** — Home Assistant (Hermes tool) — Hermes → HA → Google Home/Alexa/physical devices. Prerequisite: running HA instance. See detail below.
16. **B28** — OpenClaw rehabilitation (or retire) — **✅ RESOLVED 2026-06-25: SUPERSEDED by B66.** The keep/retire/reuse decision is no longer standalone — it's the "base agent" workstream of the consolidated [B66] Operator Agent Platform (Hermes-base vs reuse-OpenClaw's-responsiveness, decided at B66 build time). OpenClaw is NOT auto-retired (reuse candidate). Both original Qs (keep-vs-retire, refactor-vs-rewrite) move to B66.
17. **U14** — n8n workflow → git — audit active n8n workflows before working on this. See detail below.
18. **B34** — Evaluate + bake PII guard — promote B14's deferred PII validator (llm_guard `Sensitive` → presidio/spaCy) from coded-but-unbaked to active. Gated on an eval showing PII detection adds real signal in this corpus (and/or a multi-user/export trigger). See detail below.
19. **B35** — Grounding guard calibration — tune the B14 grounding validator from its guessed `0.5` threshold to a data-driven one (collect shadow `max_entailment` distribution → label grounded vs hallucinated → set threshold), and switch to sentence-level / concatenated-premise scoring if whole-answer-vs-chunk NLI over-flags. Prerequisite to ever moving grounding out of shadow. See detail below.
- **B36** — Hermes dashboard performance — ⚠ the Hermes web dashboard (+ Kanban view) is **live** at `https://dashboard.weyland.lab` but is **dog-slow**. Revisit performance. See detail below.
- **B46** — **Build out the Stud.io product backlog** — Stud.io has no backlog/roadmap yet. Assemble it (audit the repo, define epics + items), then dump into the Linear **Stud.IO** project (same treatment as the Weyland dump). Near-end maturity item. **Seed item (from the B60 Port audit, 2026-06-23):** stud.io has real **test + production** envs (containerized, Woodpecker-deployed) — wire its deploy pipeline to emit `deployment` events → Port `environment` entities (Test/Production) so the **deployment-frequency DORA** lights up for stud.io (the one DORA pillar PR/CI metrics don't cover: "how often do I ship to prod"). Cheap once the pipeline's already moving — lands naturally alongside the **B57** farm migration.
- **B73** — **Find/build uses for the datasets-lake formats** — B72's music data exists in 5 formats (Parquet/Lance/Avro/Arrow/Iceberg) but is inert; build a use case per format that exercises its strength (Lance→similarity/recommendation, Avro→Kafka stream, Parquet/Iceberg→Trino/DuckDB analytics, Arrow→polars EDA) so the format choices are validated by use. Sequence after the Tier-2 engines exist. See detail below.
- **B74** — **Hybrid retrieval (BM25 + dense fusion) in the tool-server** — value-realization of the OpenSearch BM25 work: the lexical index (`weyland_chunks`) is built + cataloged but the RAG still queries dense-only; fuse BM25 + a vector backend (RRF) in the tool-server retrieval so lexical recall (exact identifiers/config keys/commands) joins semantic recall. Validate hybrid-vs-dense on the B4 eval leaderboard; feeds B70. See detail below.
- **B77** — **Data-quality layer: asset-checks / Great Expectations → DataHub Assertions** — move data-quality *detection* upstream instead of discovering it as a crash three layers down (the `fma_tracks` URL-as-column-name was found by crashing the Lance writer; spotify's empty column by an avro-manifest failure). Note the split: *cleaning* (the `sanitize_columns` name-normalize + `coerce_null_cols` null-cast in `datasets_lib`) stays in the transform — GE/checks **validate**, they don't mutate. Start with Dagster-native `@asset_check` (schema / non-null / column-name-pattern expectations on the silver assets), graduate to **Great Expectations** suites for richer/reusable checks; emit results to **DataHub Assertions** (GE has a native DataHub action) for one-pane governance + Alertmanager/Telegram alerting. Build as a `build_asset_checks(cfg)` factory in `datasets_lib`, mirroring `build_transform_assets(cfg)` — every domain gets checks for free from the explicit `DomainConfig`. Slots into **B1.6** governance (alongside Soda DQ). GE confirmed on the roadmap. **SPLIT (2026-06-30):** (a) **native Dagster `@asset_check` layer = the pre-hydration GATE, done BEFORE data-store-mageddon** — validate the silver/gold before fanning data into a dozen stores (catch the bad-schema class once, not per-store); (b) the heavier **Great Expectations suites → DataHub Assertions** governance/alerting = the later tail, rides with/after hydration. So three `datasets_lib` factories on one `DomainConfig`: `build_transform_assets` → `build_asset_checks` → `build_store_load_assets`.
- **B47** — **Code-quality findings triage** — act on the first SonarQube/Trivy/Semgrep scans (don't let the scanners be stand-up-and-ignore). Known: 3 Dockerfiles missing `USER` (run as root — Trivy `DS-0002` + Semgrep, easy win), dynamic `urllib` in `tool-server/main.py` + `hermes/roadmap-sync.py`, H2C smuggling in `hermes/dashboard-nginx.conf`, tool-server Deployment misconfig (KSV-0118). Low-risk on a LAN-only lab but real hardening. Re-scan after fixes (entities update in Port).
- **B48** — **Observability: unified logs + traces in Grafana (Loki + Tempo)** — **DONE 2026-06-21.** Full LGTM: **Loki** (SingleBinary → MinIO) + **Alloy** DaemonSet (logs), **Tempo** (monolithic → MinIO, traces). Istio mesh tracing + Kiali repointed to Tempo; **Jaeger retired** (addon + ingress + datasource removed). Grafana Loki/Tempo datasources → Explore + Logs/Traces Drilldown. See [runbooks/observability.md](runbooks/observability.md) Phase 4. **Follow-up (B49).**
- **B49** — **Tempo metrics-generator** (span-metrics + service-graph) — the Drilldown Rate/Error overview panels show "empty ring" because Tempo's metrics-generator isn't enabled (needs Tempo→Prometheus remote-write: `metricsGenerator.enabled` + Prometheus `enableRemoteWriteReceiver`). Traces themselves work; this only adds the RED/service-graph panels. Optional polish.
- **B50** — **Port as launcher (not status board)** — DONE 2026-06-21 (recording the model change). Retired the Kuma→Port `uptime_monitor` flow (status went stale — Kuma webhook is event-only); Port now = `endpoint` blueprint (31 entities) + **Launcher** dashboard (one-click UIs/APIs). Kuma (`kuma.weyland.lab`, Telegram paging) is the live status board. Catalog cruft left as-is (istio_gateway/VS empty, k8s_pod churn, DORA defaults) — deep-clean only if Port gets noisy.
- **B51** — **APM & Alerting** (batch — **DONE 2026-06-21**) — app-observability on top of LGTM. **DONE:** (1) **GlitchTip** self-hosted error tracking (web + worker + **Valkey** — required for the cache, `valkey://` scheme; meshed Postgres; `glitchtip.weyland.lab`; [runbooks/glitchtip.md](runbooks/glitchtip.md)) with **tool-server** (project 1) + **Dagster** (project 2) instrumented via the Sentry SDK (Dagster needs the `modules` integration disabled — its big dep tree bloats events past GlitchTip's size limit → 200-then-dropped); (5) **GlitchTip → Port** webhook (`glitchtip_issue` blueprint off the Slack-attachment payload) + GlitchTip in the Launcher + **registration locked** (`ENABLE_USER_REGISTRATION=false`); (4) **Loki ruler** LogQL alert rules → existing **Alertmanager → Telegram** (one alert pipeline for metrics + logs; rules ConfigMap mounted at `/rules/fake`, threshold tunable). **Deferred:** Hermes error tracking → **B52**; Sentry SaaS + OTel app instrumentation → **Extras** (B53/B54). **Skipped:** SigNoz (duplicates LGTM), self-hosted Sentry (too heavy).
- **B52** — **Hermes error tracking (GlitchTip)** — deferred from B51. Hermes is a **third-party packaged agent** (`NousResearch/hermes-agent`, no source of ours), so instrumentation = the **injection route**: install the **mkcert root CA into CT 104** (HTTPS to `glitchtip.weyland.lab`), `uv pip install sentry-sdk` into the gateway venv (`/usr/local/lib/hermes-agent/venv`), a `sitecustomize.py` that inits Sentry (with `modules` integration disabled — big dep tree), and `SENTRY_DSN` as a real env var in the `hermes-gateway` systemd unit. High effort / lower payoff for a 3rd-party agent with its own logging — revisit if Hermes starts erroring in a way worth tracking.
- **B55** — **Cloud Cost (OpenCost) + lab cost picture** (batch — **DONE 2026-06-22**) — the Port **Cloud Cost** category (B43 follow-on) plus a full lab-TCO view. **(1) OpenCost** (CNCF, ns `opencost`, `opencost.weyland.lab`) reads the existing kube-prometheus Prometheus; **custom on-prem pricing** (bare-metal MS-A2, no cloud bill): $2500/5yr ($41.67) + ~55W @ $0.16/kWh (Wilmington=RMLD, $6.42) = **~$48/mo box**, split 50/50 CPU:RAM over 32 vCPU/96GB → k3s slice ~$15/mo. [runbooks/opencost.md](runbooks/opencost.md). **(2) LiteLLM spend meter** — already wired by B26 (`callbacks:[prometheus]` + ServiceMonitor); closed the TODO — spend metric is **`litellm_spend_metric_total`**, scrape path → `/metrics/` (307 trailing-slash), spend alert now valid → Telegram. ~$0 (free tiers; Claude is a flat sub, NOT routed through LiteLLM). **(3) Port `cost` blueprint** — categorized (infra/ai/dev-tools/domain/business) + cadence-aware `monthlyCost` calc; seeded **Claude Max $200** + infra $48 + LiteLLM $0 = **~$248/mo** (Claude ≈ 80%); OpenCost in the Launcher; a **Cost dashboard** (total + table). B50-aligned: Port = summary + launcher, OpenCost = live detail. **Deferred (maturity):** the full **subscription dump** (JetBrains, emangini.com domain, other SaaS — the categorized ledger is ready to fill); optional Prometheus→Port live-LLM-spend push.
- **B56** — **CI/CD (Woodpecker) → Port** (batch — **DONE 2026-06-22**) — the Port **CI/CD** category (B43's last category → all categories now wired) + the lab's first build automation. **Woodpecker CI** on k3s (server + 2 agents, ns `woodpecker`, `woodpecker.weyland.lab`, GitHub OAuth, SQLite) with the **kubernetes backend** — pipeline steps run as **pods in-cluster** (so pipelines can build/deploy the weyland apps). **LAN-only:** GitHub can't reach the lab for push webhooks → triggers are **manual / cron** (same wall as B30). First `.woodpecker.yml` (info + yamllint via a `.yamllint` = relaxed minus line-length) proves the backend; a `notify-port` step POSTs build status → Port **`ci_pipeline`** blueprint (id `repo-number`, history per run) via a Woodpecker repo secret `port_ingest_url` (ingest key stays out of the public repo). Woodpecker in the Launcher. [runbooks/woodpecker.md](runbooks/woodpecker.md). **Gotchas closed:** YAML colon-space (`Content-Type: …`) → use a `|` block; Port webhook mapping must be **Saved** before the event fires (no replay). **Deferred:** real build/test/deploy pipelines for the weyland images (replace manual scp+build), cron triggers → **B57**; Stud.IO migration onto the farm → **B57**.
- **B58** — **IaC (two lanes: Argo CD for k8s + OpenTofu for the rest)** — supersedes the manual-scp posture ([[deployment-approach]] now: GitOps for onboarded k8s apps). **Tool calls:** **Argo CD** (GitOps) for the **k8s** lane — chosen over Flux (the dashboard wins, footprint is noise on a 32GB box); **OpenTofu** (OSS Terraform fork) for **non-k8s** — Proxmox VMs/CTs + SaaS (Port/GitHub/DNS). NOT a direct CI→CD wire — git is the seam (handoff = B57). **(a) Argo lane — DONE 2026-06-22:** `argocd.weyland.lab` (helm, `server.insecure` behind Traefik, local admin — OIDC via Keycloak with B1); **app-of-apps** root watching `k8s/argocd/applications/`; **28 apps onboarded** (20 raw auto-sync + 8 helm multi-source, chart-from-repo + values-via-`$values`). Deploy flow = **edit → push → Argo reconciles** (scp retired). Skipped (still running, not GitOps-tracked): istio (istioctl), argocd-self, port-exporter, traefik/coredns/rbac (k3s), code-quality Jobs; headlamp deferred. [runbooks/argocd.md](runbooks/argocd.md). **Gotchas:** `ServerSideApply=true` for big CRDs (256KB annotation cap); helm `releaseName` must match the LIVE release (kube-prometheus-stack release = `monitoring`); Helm→Argo adoption shows a bigger diff — sync deliberately. **(b) OpenTofu lane — DONE 2026-06-22:** spine proven (runs from rogueone; **state in MinIO** S3 `s3.weyland.lab/tofu-state`, path-style, creds via env — `AWS_*` MinIO + `PORT_*` Port). **Port's 7 blueprints codified** (`tofu/port/`, brownfield CLI `tofu import`, clean no-op plan): cost, ci_pipeline, glitchtip_issue, feature_flag, code_quality, security_scan, endpoint. [runbooks/opentofu.md](runbooks/opentofu.md). **Gotcha (cost an hour):** port-labs provider source-type (`port-labs`) ≠ resource prefix (`port_`) → `-generate-config-out` writes `provider = port-labs` per resource → phantom `hashicorp/port-labs` poisons `init`; fix = strip those lines + CLI import (not `import` blocks). **Proxmox DONE 2026-06-22:** all **5 guests imported** (`tofu/proxmox/`, `bpg/proxmox`, API-token auth, state in MinIO) — CTs ollama/whisper/hermes (`proxmox_virtual_environment_container`) + VMs openclaw/mother (`proxmox_virtual_environment_vm`); mother's raw passthrough disk (4TB Seagate) frozen via `lifecycle ignore_changes=[disk]`. bpg gotcha: `-generate-config-out` emits write-invalid sentinels (`cpu.units=0`, `architecture/affinity/hugepages/entrypoint=""`) → omit them; `mac_addresses` computed → remove; `timeout_*` config-only. **GitHub DONE 2026-06-22:** weyland-lab repo codified (`tofu/github/`, `integrations/github`, PAT auth, CLI import). **Justified skips:** rest of Port (actions/scorecards/dashboards/entities — Port-managed defaults + integration-generated, or live *data*; NOT authored config → tofu would fight Port's lifecycle), and DNS (CoreDNS = a k8s ConfigMap, Argo's domain; no external zone). **B58 COMPLETE** — k8s (Argo, 28 apps) + non-k8s (OpenTofu: Port 7 blueprints + 5 Proxmox guests + GitHub repo) all codified; the rest of the IaC surface is either Argo's domain or not-our-config.

### Extras / Optimization
- **B57** — **Build farm: GitOps CI→CD + Stud.IO migration** — deferred from B56. **(a) GitOps CI→CD handoff (Woodpecker↔Argo, decoupled via git — NOT a direct wire):** the right model is git-as-seam, not Woodpecker calling `argocd sync` (which bypasses GitOps → drift). **Prerequisite = an in-cluster registry** (zot / distribution / k3s's) — today's `docker build` + `k3s ctr import` + static `:local`/`imagePullPolicy:Never` gives Argo no tag to diff. Flow: **Woodpecker (CI)** builds the weyland images (tool-server/dagster) → pushes a **versioned tag** to the registry → **commits that tag into the git manifests**; **Argo CD (B-IaC)** reconciles + deploys. (Argo **Image Updater** is the alt to CI-commits-the-tag.) Replaces the manual scp+build loop; + **cron** triggers (no push webhooks on the LAN); + kubeconform manifest validation as a pipeline step. Only applies to apps we **build** (tool-server/dagster) — third-party/helm apps are Argo-solo. **(b) Migrate Stud.IO** off its local Woodpecker (+ GH Actions runners on rogueone) onto weyland's shared dev/build resources — weyland Woodpecker is natively multi-repo, so add the Stud.IO repos. Keep both parallel until the weyland farm is proven.
- **B63** — **Woodpecker runs → Port (weyland CI reliability signal)** — **BLOCKED on B57** (verified 2026-06-23: the `ci_pipeline` blueprint holds exactly **1** entity — the B56 PoC run `weyland-lab #8`, manual/success — so there's no CI activity to compute a failure rate from until B57 lands real build/test pipelines; building a view now would be an empty dashboard, the exact "accurate-but-empty" trap the B60 EI audit flagged). **Then:** Port's stock Reliability/DORA-failure boards read **GitHub Actions only** → blind to weyland (runs **Woodpecker**, not Actions). Extend the existing B56 `notify-port` step (→ `ci_pipeline`) to emit a build-status/failure signal Port aggregates into a weyland reliability view. **Architecture note (B60 EI audit):** Port = delivery/DORA layer; Grafana/LGTM/Kuma = runtime/ops — keep separate; the only cross-bridge worth building is incident signals (Kuma/GlitchTip → Port) for DORA change-failure/MTTR.
- **B53** — **Sentry SaaS** (free tier) — deferred from B51 to Extras. Would add a native Port↔Sentry integration (Ocean exporter, richer than the GlitchTip webhook) + a cloud sink. **Why deferred:** GlitchTip already covers error tracking AND GlitchTip→Port works, so the only delta is shipping app errors **off-LAN to a third-party cloud** — counter to the self-hosted/LAN-only choice that picked GlitchTip over SaaS. Optional/demo-only; revisit only if a Port-native Sentry demo is specifically wanted.
- **B54** — **OTel app instrumentation → Tempo** — deferred from B51 to Extras. Instrument the Python apps (tool-server, Dagster) with the OpenTelemetry SDK → Tempo for **app-level spans** (true APM; mesh/Istio spans already flow to Tempo). Adds per-request app tracing beyond the service-to-service mesh view. Deferred: meaningful effort per app; mesh tracing + GlitchTip error tracking already cover the immediate needs.
20. **B9** — Python→Go refactor — conditional; revisit when operational pain is real or agents are modifying the codebase. See detail below.
21. **U13** — Slim sentence-transformers image / ONNX evaluation — deferred decision point: evaluate (a) swap to ONNX only, (b) both sentence-transformers + ONNX, or (c) stay with sentence-transformers. Depends on whether active embedding model experimentation is in progress at the time. See detail below.
22. **B22** — SearXNG — Extra; Tavily works fine. See detail below.
23. **B18** — Spotify (Hermes tool) — Extra. See detail below.
24. **U16** — Weaviate UI — Extra; evaluate whether still needed (native Weaviate UI may suffice). See detail below.
25. **B30** — Real-time docs ingestion trigger — self-hosted GitHub Actions runner on the LAN fires Dagster `launchRun` on push (NAT-free near-real-time). Deferred; cron fine until 15-min latency bites. See detail below.
26. **B32** — NeMo Guardrails evaluation — programmable conversational guardrails (Colang DSL: topical/dialog/jailbreak rails). Deferred from B14 (heavy framework + new language; built for dialog mgmt, not I/O scanning). Evaluate for the **Layer-2 agent layer** (Hermes dialog/topical rails), not the tool-server I/O pipeline. See detail below.
27. **B38** — **Fuzzy GraphRAG: LLM concept/entity extraction** over the AIDLC KB (and `docs/`) — extract entities + *emergent* relationships from **prose** (beyond the declared frontmatter links) into Neo4j, à la Microsoft GraphRAG. **Deferred from B37**, which ships the deterministic frontmatter graph (`RELATED_TO`/`SURFACES_AT`/`TAGGED`). Why deferred: heavy on local CPU Ollama (517 docs × extraction passes, re-run on change), fuzzy/non-deterministic, needs an entity/relation schema + canonicalization/dedup ("DDD" = "Domain-Driven Design"), and low marginal value while the author-declared frontmatter already yields a high-precision graph for ~free. **Revisit once** B37 proves corpus value AND/OR a bigger model / GPU lands (pairs with B7 eGPU / B33).

28. **B44** — **Grafana OnCall** (incident lifecycle) — deferred Extra. Adds structured incident timeline + postmortem log on top of existing Alertmanager→Telegram alerting. Cruft: 2 always-on pods (oncall + celery) + Redis + a Postgres DB role. **Gate:** only worth it if a real multi-service incident workflow need emerges (escalation chains, on-call rotation, postmortem process). At N=1 with Telegram already covering paging, this is a "do we ever actually use it?" bet. If it hasn't been stood up by the time the data mesh + agent platform are stable, **drop it entirely**. Grafana plugin enable only — no new Grafana pod.

29. **B45** — **Hermes incident-response (agent-in-the-loop)** — deferred Extra. Let Hermes *enrich + act on* incidents (correlate, dedup, "tool-server down → here's the last log → restarted it") rather than just raw "X is down" pings. **Hard constraint:** consume incident signals **off the critical alert path** (read from Port, or a fan-out) — **never** route Kuma→Hermes→Telegram, because monitoring must not depend on an agent that can itself fail (Hermes is outbound-only today + the fragile layer). Direct Kuma→Telegram stays the paging path. Gated on the agent platform maturing.

30. **B39** — **Design→code workflow (Figma → code)** — stand up a design-to-code pipeline using the **Figma MCP** (already available in-session): pull Figma designs/components into implemented UI code (and optionally code→Figma sync). Gives the lab's UI surfaces — U16 (Weaviate UI), B3 (Backstage), future dashboards — a consistent design system instead of ad-hoc per-tool UIs. $0: Figma has a free tier. **Open:** (1) Figma account + design system/tokens; (2) which UI to target first; (3) where design artifacts live (a `design/` area in the repo?); (4) Figma-MCP auth in headless/cron vs interactive-only.

29. **B40** — **Mermaid rendering in TechDocs (B3 IDP)** — our `docs/` mermaid diagrams render as code blocks in the IDP's TechDocs (GitHub renders them fine, so no urgency). No official Backstage Mermaid addon exists. **Revisit approach (user-set):** (1) **try the community frontend plugin first** (`backstage-plugin-techdocs-addon-mermaid`) — interactive client-side render, but wiring it into the **new frontend system** is the risk; (2) **if that fails, fall back to build-time SVG pre-render** (`mkdocs-mermaid-to-svg` + mermaid-cli → static vector SVGs, no frontend change; optionally the official **LightBox** addon for click-to-zoom). Catalog graph + TechDocs themselves already work — this is the one parked polish item.

30. **B41** — **Self-syncing IDP (B3)** — ✅ **DONE 2026-06-19.** The IDP now tracks the repo with no manual republish. **Catalog** read live via `catalog.locations: type: url` off public GitHub (Backstage UrlReader polls ~150s; `integrations.github: [{host: github.com}]` for the unauthenticated public read; the catalog ConfigMap is **deleted** — repo is the only source of truth). **TechDocs** built+published hourly by a Dagster job (`weyland_techdocs_job` / asset `techdocs_publish`: pure-Python `mkdocs build` + `minio` upload → `techdocs` bucket; **no `@techdocs/cli`, no node**). Two mechanisms on purpose: the catalog needs no build (fetch live), TechDocs does (build+publish). Runbook [runbooks/weyland-idp.md](runbooks/weyland-idp.md). Catalog target: `github.com/edtbl76/weyland-lab/blob/main/nodes/mother/lab/weyland-platform/catalog/weyland-catalog.yaml`.

31. **B42** — **IDP Scaffolder execution (B3 slice C)** — the golden-path template **lists** in the IDP but **can't run**: `fetch:template` + `publish:github:pull-request` hit the GitHub **API**, and this Backstage image's **node-fetch v2 throws `ERR_STREAM_PREMATURE_CLOSE` on gzipped responses** (`Gunzip` in the stack). The catalog read works because it uses `raw.githubusercontent.com` (uncompressed); the API path doesn't. **Revisit options:** (a) force `Accept-Encoding: identity` on the github integration fetch; (b) bump/patch Node or node-fetch in the image; (c) **sidestep GitHub** — bake the skeleton into the image (a ConfigMap can't hold the nested tree) + render-to-download, no PR/PAT (also removes the token that took the catalog down tonight). Token reverted, so the catalog is back on unauthenticated read. Files live (uncommitted): `catalog/templates/k8s-service/`.

32. **B43** — **Port.io IDP migration** (replacing Backstage) — **IN PROGRESS 2026-06-20.** Port.io (SaaS, EU, Free tier — `app.port.io`, org `org_KyCTEN4PVUv1D3TM`) is the zero-maintenance IDP replacement for Backstage. **Live:** K8s exporter (`weyland-cluster` — full cluster topology: namespaces/nodes/workloads/replicasets/pods + Istio Gateway/VirtualService CRDs), GitHub exporter (`github-weyland` — 6 repos, Port-side IN() filter to exclude public repo GitHub-app loophole). **Live exporters:** K8s (`weyland-cluster`), GitHub (`github-weyland`), **Uptime Kuma** (`uptime-kuma` webhook → `uptime_monitor` blueprint, **16 monitors**, `kuma.weyland.lab`; [runbooks/uptime-kuma.md](runbooks/uptime-kuma.md) — needs LAN CoreDNS + mkcert CA mount), **Linear** (roadmap status tracking — issues/teams/labels; stock integration has no project/label-name support, accepted for status-only use), **Unleash** (Feature Management — `unleash` webhook → `feature_flag` blueprint, `unleash.weyland.lab`; self-hosted OSS, meshed to STRICT Postgres, flag enable/disable events ingested; [runbooks/unleash.md](runbooks/unleash.md)), **SonarQube + Trivy + Semgrep** (Code Management — `code_quality` + `security_scan` blueprints; SonarQube server `sonarqube.weyland.lab` + on-demand Trivy/Semgrep scan Jobs; [runbooks/code-quality.md](runbooks/code-quality.md)). **Categories wired so far:** Kubernetes, Istio, GitHub, Incident Mgmt (Uptime Kuma), Project Mgmt (Linear), Feature Mgmt (Unleash), Code Quality (SonarQube/Trivy/Semgrep). **Roadmap split:** this `backlog.md` = design/ordered source of truth; Linear (`emangini` workspace, 3 projects) = task status; Claude syncs Linear via MCP **ad-hoc at end of each batch** (no auto-sync); Hermes→Linear parked (B45-era). **Also landed this batch (supporting infra):** KEDA (autoscaling/run-mode engine for the data mesh — B1), prometheus-pve-exporter (Proxmox metrics → Grafana #10347), Jaeger+Alertmanager Grafana datasources (traces+alerts in Grafana), mother VM 16→32GB / 4→8 vCPU, Kuma 16→23 monitors. **All B43 categories now wired** (Cloud Cost = B55/OpenCost, CI/CD = B56/Woodpecker, both DONE 2026-06-22). **Decom DONE (B59, 2026-06-22):** Backstage torn down after Port reached catalog parity — app + 12 `backstage_plugin_*` DBs + `weyland_idp` role + MinIO `techdocs` bucket + `weyland_techdocs_job` Dagster asset all removed. B42 moot. **B43 effectively complete — Port.io is the IDP.**

### Next — finish Port, retire Backstage (the two big steps after B58)
- **B59** — **Backstage → Port parity, then RETIRE Backstage** — **✅ DONE 2026-06-22.** Reached full catalog parity in Port *first*, then tore Backstage down. Catalog: 5 custom blueprints (`domain`/`system`/`component`/`resource`/`api`) + **26 entities** (1 domain · 3 systems · 11 components · 6 resources · 5 APIs) + dependency graph + **the upgrade Backstage couldn't do: live `component → k8s_workload` links** — built via MCP, **codified in `tofu/port/catalog.tf`** (gotcha: `port_entity` generate-out emits `provider = port-labs` + read-only `id/created_at/updated_at/updated_by` → strip both). Sidebar → a **Software Catalog** folder. Docs: a **standalone MkDocs Material site** (`docs.weyland.lab`, `k8s/docs-site/`, initContainer-builds + nginx) — browsable+searchable, **Mermaid renders (closes B40)**. Retire: Backstage app + 12 `backstage_plugin_*` DBs + `weyland_idp` role + MinIO `techdocs` bucket + `weyland_techdocs_job` Dagster asset all removed. B40 + B42 moot. **Plan as executed:** **(1) Parity audit** — enumerate what Backstage actually serves today (slices A+B: Software Catalog entities from `catalog/weyland-catalog.yaml`; **TechDocs** = the rendered `docs/` site; **Catalog Graph** = entity relations; the **API catalog** mirrored in `docs/api.md`) and confirm Port covers each — or consciously drop it. Known decision point: **TechDocs has no native Port equivalent** (options: drop it / link the GitHub-rendered docs from a Port page / keep MkDocs standalone). Catalog entities ≈ Port's K8s + GitHub exporters + blueprints; catalog graph ≈ Port relations (native). **(2) Retire** — once parity is signed off, tear down `k8s/weyland-idp/` + the `weyland_techdocs_job` Dagster asset + MinIO `techdocs` bucket + IDP Postgres role + ConfigMaps + the `idp.weyland.lab` ingress; flip arch/api/hosts/backlog Backstage → **RETIRED**. B40 + B42 (Backstage Mermaid/scaffolder) become moot. **Big step — own block.**
- **B60** — **Master + build out Port** — **Phase 1 audit COMPLETE; Phase 2: scorecards DONE (→B61), self-service actions + workflows DEFERRED** (Linear EMA-49). Walked the whole sidebar (wizard dismissed; Quick Access; Engineering Intelligence; Manage Scorecards; Manage AI Assets; Builder workflows/automations). Pruned 9 redundant scorecards, the empty AI-Adoption dashboard, + a dead `ai_adoption_low_alert` Slack automation; kept the relation-wiring plumbing automations + 4 stock AI agents. Catalog tables intentionally skipped. **Architectural decision 2026-06-24 — Port = the "see" layer** (catalog/scorecards/dashboards/observability), **Hermes = the "do" layer** (acts on the lab via the tool-server): self-service actions deferred because Port's cloud **can't reach the LAN** to run infra actions (same wall as GitHub webhooks → would need a self-hosted Port execution agent), and Hermes already does ops; workflows have nothing to chain yet. **Spinoffs:** B61 (scorecards→Gold, done), B62 (AI-Dev Usage data product, done), B63 (Woodpecker reliability, blocked on B57). **Remaining (minor):** deep-audit Plan-my-day/Manage-incidents (stock), optional operator-cockpit dashboard.
- **B61** — **All `service` entities → Gold on Production Readiness** — **✅ DONE 2026-06-24** (core work; some repo artifacts a `git push` away; Linear EMA-50). **Customized the `production_readiness` scorecard for a PUBLIC solo lab:** dropped the `github_private_visibility` Silver rule (no public repo can ever pass it) so Gold is reachable; kept the rest of the ladder (Bronze README/.gitignore/url/language/team · Silver active-30d/criticality/PR-template · Gold CODEOWNERS/active-7d). **Pruned 9 redundant stock scorecards** (org/group/team-DORA duplicates — noise at N=1); kept the 6 service-level + Availability + Sonar. **weyland-lab artifacts created** (root `README.md` + `CODEOWNERS` + `.github/pull_request_template.md`); same 2 files staged into stud.io/emangini/midi (the active repos) — on push + GitHub resync those → **Gold**; algopedia + service-transformation left dormant (don't fake commits for a badge). **Value = defining production-ready for THIS lab, not the badge.**
- **B62** — **AI-dev usage data product → Port** — **✅ DONE 2026-06-24** (B37/aidlc-kb pattern; Linear EMA-51). Custom **`ai_session`** blueprint (project, duration, turns, input/output/**cache**/total tokens, models, tools-invoked, **`api_equiv_value_usd`** = what pay-per-use WOULD cost — you're on a subscription, so it's the *value* flex: ≈$12K across all projects, $0 actually spent). **Two-stage, mirrors B37 exactly:** (a) **producer** `nodes/mother/lab/weyland-platform/scripts/ai_session_feeder.py` on rogueone parses `~/.claude/projects/**/*.jsonl` → per-session summary JSON (**metrics only — no conversation content**) → `mc mirror` to MinIO `ai-sessions/`; (b) **Dagster asset** `ai_session_ingest` (group `ai_session`, 4h schedule + on-demand, B37 empty-read guard) reads MinIO → upserts to Port. Scope = relevant repos only (weyland-lab, stud.io, midi_real_book[+Etudes folded in], emangini-tailwind); weyland-lab/stud.io ai_sessions relate to their `service` entity. **Token gotcha:** `cache_read` is re-counted every turn → summing balloons to billions; headline **output_tokens** (real generation), keep cache as its own fields. **Dashboard:** "AI-Dev Usage" (Port). Producer cron + Dagster schedule keep it fresh. Dagster is the data-mesh-proper home (ties to B1).
### Hardware-Gated
33. **B21** — Agent media generation (image/video/TTS) — requires eGPU hardware purchase. See detail below.
33. **B33** — Co-resident / warm-parallel model serving — raise `OLLAMA_MAX_LOADED_MODELS` (now 1, cgroup-bound) to keep a 2nd model warm alongside the main one → eliminates eviction/cold-start for latency-sensitive multi-model workflows (e.g. B14's conversational grounding guard, or guard+generator both warm). Gated on RAM/VRAM headroom (the "weyland box" decision / eGPU). See detail below.

---

## Tentative / someday
- **weyland eGPU (OCuLink + 24 GB GPU)** — accelerates the Ollama path (~10× on ≤32B models),
  but **not pursuing now** — CPU/Ollama is sufficient for the lab; user will invest eventually if
  a workload makes the speed worth it. Full options + (unverified) pricing in
  docs/concepts/model-serving-hardware.md. Revisit when an actual workload feels too slow.
- **Evaluate GPUs specifically for music / TTS / audio-generation models** — these are
  diffusion/audio architectures that **do NOT run under Ollama** and are **GPU-hungry**
  (slow-to-unusable on CPU): MusicGen / Stable Audio (music), XTTS / Bark / Kokoro (TTS). An
  audio-generation goal is one of the few workloads that genuinely *justifies* the eGPU above —
  so if audio becomes a goal, fold its VRAM / throughput needs into that eGPU decision (sizing
  may differ from LLM needs). **Exception:** Whisper **STT** (speech→text) runs fine on CPU via
  whisper.cpp — no GPU needed; only *generation* (text→audio) wants the GPU.
- *(Promoted to numbered units — see detail below: Hermes media-gen tools → **B21**; Home Assistant →
  **B20**; SearXNG → **B22**. The eGPU + audio-gen-GPU items above remain Tentative as hardware decisions.)*
- **Benchmark 70B-class models on the Ollama/CPU path** — pull a 70B@Q4 (e.g. `llama3.3:70b`,
  ~43 GB, fits the 48 GB container cap) and record the real `eval rate` to validate the
  "batch/async capacity tier" (expect ~1–2 tok/s — kick-off-and-walk-away). Deferred: large
  download + slow, no need yet. Fills the 70B row in the measured-benchmark table in
  docs/concepts/model-serving-hardware.md. Requires the `num_thread 8` fix like every model.

---

## B-item and U-item detail sections

### B37 — Ingest the AIDLC knowledge repositories into the (Graph) RAG — ✅ DONE 2026-06-19
**Follow-on (DONE 2026-06-19): Neo4j GDS** — enabled the free Graph Data Science plugin (`NEO4J_PLUGINS` in
`k8s/neo4j.yaml`) and ran graph algorithms over the `:Entry` graph: **PageRank** surfaces load-bearing concepts
(event-driven-architecture, ci-cd, microservices, domain-driven-design…), **Louvain** auto-clusters the 510
entries into ~8 coherent themes. Commands + baseline in the runbook. **Visual: NeoDash deployed**
(`http://mother:30088`, `k8s/neodash.yaml`) — free Bloom-alternative that works with Community (Bloom itself
needs Enterprise/Aura; Neo4j Desktop dev-license path was parked).
**Goal:** feed the three AIDLC knowledge bases into the multi-backend RAG so the lab can reason with
*domain knowledge*, not just its own infra docs — "make this bad boy MUCH smarter" (user, 2026-06-18). Consumers:
Hermes + Claude Code via the system-view MCP `context_ask`/`context_search`, the eval harness, future agents.
- **Corpus:** `engineering-knowledge-repository` (397 md), `consulting-tools-repository` (62), `industry-vertical-repository`
  (58) = **~517 markdown files**, ~13× today's `docs/` corpus (40). Each repo is taxonomy-indexed (an `index.md`
  + entry files keyed by stage / vertical, with cross-references).

**The sourcing problem — ✅ DECIDED 2026-06-18 → Option 2 via MinIO + brand-neutral.** The content is the
**user's own IP** (they authored the Method AIDLC + the 3 KBs — *no* license/redistribution issue; the missing
LICENSE file made it merely *look* third-party). Chosen path: **keep `.methodaidlc/` out of the repo**, scrub
brand mentions, drop a **brand-neutral copy into a private MinIO bucket (B6)**, and add a Dagster asset that
reads from S3 — decoupled from the GitHub-clone path. **Option 1 (un-gitignore + push) rejected**: user wants
brand-neutral output and the methodology kept out of the repo. Original framing + options retained below for
context. `.methodaidlc/` is **gitignored** (`.gitignore:97`), so it's **not on GitHub**, and the B25b ingestion
shallow-clones from GitHub (`source_document.py`) — it can't see these repos. Options were:
1. **Un-gitignore + push to GitHub** + extend `source_document.py` to ingest the three repo paths as markdown.
   Simplest mechanically — but it publishes **third-party AIDLC framework content** to the repo; **check
   license/appropriateness** before pushing publicly.
2. **Separate local ingestion source** — a Dagster asset (or one-off loader) that reads the `.methodaidlc/` repos
   directly. But Dagster runs in-cluster (mother) and these live on rogueone/gitignored → needs a way to get them
   to mother (a private mirror, an object-store drop, or a local path mount). More plumbing, keeps them private.
3. **One-time bulk load** — the AIDLC knowledge is fairly static, so a single curated embed run (not the 15-min
   cron) may be the right cadence; re-run only when the repos update.

**GraphRAG angle (the "smarter" payoff):** these repos are *highly structured* (stage/vertical taxonomies, entry
IDs, cross-references) — a strong case for **richer Neo4j entity/relationship extraction** (currently the graph is
just Document/Chunk + sequential edges; entity extraction was deferred). This item naturally **motivates /
pairs with the GraphRAG-extraction enhancement** so the knowledge is queryable as a graph, not just chunks.

**Open questions:** (a) ✅ **DECIDED** — sourcing = MinIO + brand-neutral scrub (see above); (b) wholesale vs
curated ingest (all 517 vs index + selected entries); (c) ingestion cadence (one-off vs scheduled); (d) whether
to enhance Neo4j extraction now or chunk-ingest first; (e) **eval-corpus impact** — B4 evals run over `docs/`
markdown; decide whether AIDLC knowledge joins the eval corpus or is scoped out (it would 13× and reshape it);
(f) ✅ **DECIDED** — H2-split entry files (consistent `## What It Is / When to Use / …` structure), carry
`tags`/`surfaces-at`/`complexity` frontmatter as chunk metadata, and **do NOT vector-chunk the `index.md`/
`README` files** (they feed the graph instead); (g) ✅ **DECIDED — strip ALL brand "Method"** (user, brand
neutrality matters). Measured reality: standalone brand "Method" appears **532× across 430 of 517 files** (the
user's "there shouldn't be any" was wrong; 0 lowercase common-noun "method/methodology" uses, so no ambiguity
there). Implemented as a **curated replacement map with a PRESERVE-LIST**, applied to a staging copy (never the
live `.methodaidlc/` source). **Preserve (technical terms, NOT brand, ~28):** `Template Method` ×15,
`Factory Method` ×8 (GoF patterns), `USE Method` ×2, `RED Method` ×2 (perf), `…Analysis Method` (ATAM).
**Strip/genericize (~500):** `Method's`→"our/the", `Method recommends/uses/…`→passive, `Method engagements`→
"engagements", and the dominant header **`## Method Application` ×61** → e.g. `## In Practice`. A blind
`s/Method//` is rejected — it would corrupt the GoF pattern names. Review the diff before upload.

**Decided shape (2026-06-18):** Phase 1 chunk-ingest all 4 backends (parity with `docs/`); Phase 2 (same item)
deterministic Neo4j edges from frontmatter — `(:Entry)-[:RELATED_TO]->(:Entry)`, `-[:SURFACES_AT]->(:Stage)`,
`-[:TAGGED]->(:Tag)`, industry `vertical` nodes (513/517 entries carry `related`+`surfaces-at`). LLM-based
concept/entity extraction from prose is **deferred to B38** (Extras/Optimization — cost on local CPU Ollama,
fuzzy/non-deterministic, diminishing returns given the author-declared frontmatter links). **Deliverable:** an
on-demand ingest **runbook** `docs/runbooks/aidlc-kb-ingest.md` (scrub → upload to MinIO → trigger Dagster
asset → verify counts) — on-demand cadence means the steps must be written down.

### B1 — Build a data mesh
Domain-oriented data products + federated governance over the backends
(pgvector/Qdrant/Weaviate/Neo4j + Dagster). Depends on B6 (done), reuses B10+B16 (MLflow).

**Architecture SCOPED 2026-06-20 (directional)** → `aidlc-docs/data-mesh-design.md` (full 8-layer stack +
run-mode tiers). Headline: lakehouse on **MinIO + Iceberg + Nessie + lakeFS**; **Trino** federation;
**Dagster + dbt + SQLMesh + dlt/Debezium** transform/EL; **DataHub** catalog/contracts; **Keycloak + Ranger +
OPA** governance; **OpenLineage**, **Soda** DQ; **Cube** + dbt SL; **Lightdash + Superset** BI;
**JupyterHub + Feast + Ray** DS — heavy tiers **on-demand via KEDA** (one node). Dropped: Airflow, Airbyte,
Amundsen, ODM, Marquez, InfluxDB, Metabase.
**Next:** sequence into slices (storage → catalog/governance → query → transform → consumption); map onto the
3 data products (model-eval first — MLflow + eval store already exist). Picks may swap at implementation.

### B2 — Hermes (agent platform, sibling to OpenClaw)
**SCOPED 2026-06-13 — full design: docs/concepts/agent-platform-design.md.** Hermes = NousResearch/hermes-agent
(MIT, MCP-capable, provider-agnostic → runs on local Ollama `/v1`). **Lanes:** Hermes = **primary**
autonomous system-view/ops agent + single front door (stable, Python/local-inference-native); OpenClaw =
**contained delegate** for skill breadth/channels, **off the critical path** (firsthand fragility — gateway
broke twice during B11/B13). **Integration = 3 wires:** (1) both agents' brain → Ollama `/v1`; (2) both →
**one "Weyland system-view" MCP server** fronting the tool server (RAG, status, observability, later
workflow actions) — the "view into the system", built once, N+M not N×M; (3) Hermes → OpenClaw gateway as an
MCP tool (topology 3, **deferred**). **Hosting:** Hermes in its **own isolated LXC CT** (code-exec +
untrusted-content blast radius; not on mother, not co-located with OpenClaw). **v1 = read-only** (observe:
RAG/health/metrics); **read+act gated on B14**. **Protocol:** MCP for everything incl. the OpenClaw bridge;
**A2A deferred → B17** (only for async peer-delegation as the fleet grows). **Validate early:** local-model
tool-calling reliability (qwen3-coder:30b / qwen3:30b-a3b / mistral-small3.2:24b advertise tools); agentic
model ≠ B4 RAG winner. **First slice:** isolated CT → Hermes on Ollama → validate tool-calling → minimal MCP
server (RAG+status) → one chat channel → end-to-end.

**Status (2026-06-14): Hermes scope DONE; OpenClaw descoped → B28.** Tool-server `/mcp` up (406); Telegram
front door live (confirmed); **Hermes↔MCP confirmed working** (user-confirmed 2026-06-14 — just not yet from
Claude Code, which is **B29**). The "no weyland MCP / direct-probe" failures were **OpenClaw-gateway-specific**
(degraded gateway: MCP not surfacing to its brain, no command owner, claude-cli auth expiring, memory search
off, plaintext secrets) → **all moved to B28 (deprioritized).** The stale **weyland-postgres services
inventory** → folded into **B25** scope. read+act → B14; A2A stays B17.

### B3 — Internal Developer Platform (IDP) — slices A+B DONE 2026-06-19 (C parked → B42)
Backstage / Port / alternatives — catalog, golden paths, scaffolding. Taken on as a deliberate **learning
project** (not because service/dev count demands it yet). Built tool-neutrally (`weyland-idp`, `idp.weyland.lab`,
image `weyland-idp:local`) so the IDP tool can be swapped without renaming. Phased: **A** catalog → **B** TechDocs
→ **C** Scaffolder template.

- **✅ Slice A — Software Catalog (LIVE 2026-06-19).** Scaffolded Backstage (`services/weylandidp/`, new
  frontend+backend system, Node 22/24, Yarn 4). `catalog/weyland-catalog.yaml` = ~24 entities (Domain → 3
  Systems → 9 Components / 6 Resources / 5 APIs, wired with providesApis/dependsOn). On mother behind Traefik
  (`idp.weyland.lab`), guest auth, reuses the shared Postgres (`weyland_idp` role, CREATEDB). **Build-from-git:**
  multi-stage Dockerfile (builds from committed source inside Docker — host needs only Docker). Config via
  ConfigMap (catalog was a ConfigMap too, until **B41** moved it to `type: url` off git). Runbook
  [runbooks/weyland-idp.md](runbooks/weyland-idp.md).
  Two gotchas solved: pod must be **meshed** for STRICT Postgres (`read ECONNRESET` otherwise — [[postgres-strict-needs-mesh]]),
  and guest auth needs `dangerouslyAllowOutsideDevelopment: true` in production.
- **✅ Slice B — TechDocs + Catalog Graph (LIVE 2026-06-19).** `docs/` renders in-app as TechDocs: built
  externally (`mkdocs.yml`, techdocs-core) → MinIO `techdocs` bucket → Backstage serves it
  (`techdocs.builder: external` + awsS3 publisher → MinIO; entity `weyland-docs`). *(Initial publish was a manual
  `techdocs-cli` run; **now auto-published hourly by a pure-Python Dagster job — B41**.)* **Catalog Graph** plugin
  (`@backstage/plugin-catalog-graph/alpha`) added — per-entity relations render. **THE hard-won fix (hours of
  debug):** the new-backend default `compression()` middleware gzips+chunks responses (no Content-Length), and
  the internal **node-fetch v2** client (techdocs/search → catalog) throws `ERR_STREAM_PREMATURE_CLOSE` reading
  chunked bodies (browsers are fine) → every TechDocs page 500'd. Fix = override `rootHttpRouterServiceFactory`
  in `packages/backend/src/index.ts` to **drop `middleware.compression()`** (a rebuild WITHOUT this silently
  reintroduces the bug — see runbook). Ruled out first, in order: Istio (iptables proved port 7007 + 127.0.0.1
  RETURN'd — loopback bypasses Envoy), Node/OS version (24/trixie→22/bookworm), DNS (`127.0.0.1`/svc-FQDN). It
  was never transport. Mermaid-in-TechDocs parked → **B40**.
- **⏸ Slice C — Scaffolder golden-path template (BUILT, PARKED → B42).** The "New k8s service" template
  (`catalog/templates/k8s-service/`, `kind: Template` + Nunjucks `skeleton/`) renders a meshed Deployment +
  Service + Ingress (Traefik TLS) + `catalog-info.yaml` + a runbook stub at their real repo paths, then opens a
  **GitHub PR** (`publish:github:pull-request`). Frontend `@backstage/plugin-scaffolder/alpha` wired into
  `App.tsx` (app rebuild); backend scaffolder plugins already present. PR auth = fine-grained PAT
  (`integrations.github[].token: ${GITHUB_TOKEN}`, `weyland-idp-secret`, `optional`). Template self-registers via
  a `Location` in the catalog → auto-syncs (B41), and the template **lists** in the IDP. **BLOCKED:** execution
  fails — `fetch:template` + publish call the GitHub **API**, where this image's **node-fetch v2 chokes on gzip**
  (`Gunzip … Premature close`) — same class as the slice-B internal bug, on the external path. Parked → **B42**.
- **Later:** the "MCP harness" angle (catalog the agents/MCP as entities); absorbs B12 (API catalog).

### B4 — LLM eval / observability
**IN PROGRESS. DECIDED 2026-06-12 — Ragas REJECTED**: broken in current release (`ragas 0.4.3`
hard-imports a `langchain_community.chat_models.vertexai` path that `langchain-community 0.4.2`
deleted → won't import; fix unmerged) **+** ~100-package bloat incl. the Google Cloud AI Platform
SDK. Receipts + full decision record in **docs/runbooks/eval-harness.md**. Eval uses **direct-prompt
question-gen + LLM-as-judge scoring** via Ollama (reuses Postgres/Dagster/Ollama/bge). Steps 1–2
(schema + question-gen) live; run-matrix + scoring + leaderboard remain. Observability (Langfuse,
slice 2) still open — landscape below.

**Two complementary jobs** (LangSmith bundles them; the self-host world splits them):
- **Observability / tracing** — watch prompts, responses, tool calls, latency, cost, RAG retrievals:
  - **Langfuse** ⭐ — go-to self-host LangSmith replacement: tracing + prompt mgmt + eval + datasets;
    framework-agnostic (works with the OpenAI-compatible Ollama/tool-server); Postgres-backed.
  - **Arize Phoenix** ⭐ — best for RAG debugging: OpenInference/OTel traces, retrieval/embedding
    analysis, **native LlamaIndex integration** (already in use). Local container.
  - Helicone (proxy-style logging/cost/cache); Langtrace / Lunary (OTel alternatives).
- **Evaluation** — score output quality:
  - **Ragas** ⭐ — RAG-specific metrics (faithfulness, answer relevancy, context precision/recall) —
    directly scores `/context/ask`. Also: DeepEval (pytest-style), Promptfoo (CLI + red-team), TruLens.

**Decision:** **LangSmith is SaaS + LangChain-tuned** — data leaves the LAN and our stack is
LlamaIndex + OpenAI-compatible, so its main edge doesn't apply. **Self-host fits the LAN-lab ethos.**
**Lean: Langfuse (observability + prompt mgmt) + Ragas (RAG scoring)**, with Phoenix as the
RAG-trace-focused alternative/complement. Leans on B5 (Grafana already up). **Payoff:** measure
*which of the 6 Ollama models* answers best through the RAG — turning "they all run" into "this one
wins for this query type."

### B5 — Prometheus / observability stack
Prometheus + Grafana (+ Alertmanager). Endpoints already emit (APISIX prometheus plugin,
CoreDNS `:9153`). **Phase 1 DONE 2026-06-09** via kube-prometheus-stack (release
`monitoring`, ns `monitoring`): Grafana behind Traefik TLS at grafana.weyland.lab, admin
via grafana-admin secret (weyland_dev_password), Grafana set strategy:Recreate, Alertmanager
on. Out-of-box cluster/node/pod dashboards working. Manifests: k8s/monitoring/
{kube-prometheus-stack-values.yaml, grafana-ingress.yaml}. Runbook docs/runbooks/observability.md.
**Phase 2 (pending):** ServiceMonitors for app emitters (APISIX, CoreDNS, Traefik, Qdrant,
Weaviate; may need serviceMonitorSelectorNilUsesHelmValues:false) + Alertmanager receiver
→ n8n webhook → Telegram. Note: Grafana first-load behind the proxy needs a hard refresh
(cached partial assets → "Error loading: <panel>").

### B6 — MinIO object storage
S3-compatible storage for model artifacts, datasets/data-lake, backups, LLM/data-mesh
artifacts. Foundational (B1/B4/B7). Deploy on mother/k3s (RWO + `strategy: Recreate`,
see [[k8s-rwo-recreate-strategy]]).

### B7 — Larger models on weyland (the MS-A2)
**Full decision record: docs/concepts/model-serving-hardware.md.**
Reality (corrected 2026-06-11): weyland = the **MS-A2** (Ryzen 9 9955HX, 96 GB RAM, **no compute
GPU**), bought specifically to host large models. rogueone has the only GPU (RTX 5000 Ada Laptop,
**16 GB** — too small, and it's the personal laptop). **Decided: CPU path via Ollama is COMMITTED
and BUILDING NOW** (96 GB RAM fits 70B@4-bit; OpenAI-compatible API → drops into the harness with
no client changes; sweet spot 14–32B, 70B for batch). **Tentative/someday (low priority): an
OCuLink eGPU** to accelerate (~10× on ≤32B) — see Tentative section. Not pursued now; the lab
doesn't need the speed yet. Engine: Ollama on CPU now, vLLM if a GPU is ever added.

### B8 — Istio (service mesh) — ✅ DONE 2026-06-18
Deferred in U9 (cellular front-door decision); re-opened and **decided build-now** — all four drivers apply
(mTLS/zero-trust, mesh observability, traffic management, hands-on learning). **Design + plan:**
`aidlc-docs/construction/b8-istio-design.md`. Shape: **Approach 1** — sidecar mode, first slice =
tool-server + 4 vector backends via per-workload injection (not ns-wide), bookinfo warm-up, **step-0
mother-headroom gate** (pivot to ambient if tight). Key constraint: **slice 1 = PERMISSIVE everywhere** — the tool-server serves external NodePort MCP clients
(Hermes + Claude Code) *and* the 4 backends serve un-meshed Dagster (ingestion/eval), so STRICT would break
either; **STRICT enforcement deferred to slice 2** (mesh Dagster → flip backends STRICT). **Traefik stays the
ingress** (no Istio gateway in slice 1). Reversible per-workload. See [[architecture-decisions]].
- **✅ SLICE 1 MESHED & VALIDATED 2026-06-18:** istiod (minimal) + Kiali + Jaeger up; **qdrant + weaviate +
  weyland-tool-server** meshed (`2/2`), PERMISSIVE, **mTLS locks visible in Kiali** on the tool-server↔backend
  hops, **MCP intact** through Envoy (initialize handshake + streaming survived), no platform regression.
  **Injection mechanism correction:** per-pod injection in an *unlabeled* namespace needs the pod **label**
  `sidecar.istio.io/inject: "true"` (matched by the `object.sidecar-injector` webhook) — the *annotation* is a
  no-op outside an `istio-injection=enabled` namespace. Rollback = set the label `"false"` + rollout.
- **✅ Slice 1b DONE 2026-06-18 — neo4j + Postgres meshed.** The TCP-protocol break (Bolt 7687 / pgvector
  5432 mis-parsed as HTTP — confirmed live on neo4j: `defunct connection`) was fixed by **`appProtocol: tcp`
  on the neo4j Bolt + Postgres Service ports**, then meshing both with the inject **label**. Validated: both
  `2/2`, `/status` neo4j + pgvector `ok`, and the **un-meshed Dagster → meshed Postgres write path works**
  (`psycopg2` from `dagster-user-code` read `rag_chunks: 439`). **All four backends + the tool-server are now
  meshed (PERMISSIVE).**
- **✅ Slice 2 (STRICT) DONE 2026-06-18.** Dagster meshed (all 3 pods — gRPC code-location via the named
  `grpc` port + external egress to Ollama CT 102 / GitHub survived). Client audit: the vector backends have
  *un-meshed* clients (Prometheus app-metrics — qdrant on the shared `:6333`, weaviate on `:2112` — + NodePort
  admin access), so **STRICT was scoped to Postgres** (the clean case: in-cluster only, no metrics scrape,
  clients = tool-server + Dagster, all meshed). `k8s/istio/peerauth-postgres-strict.yaml`. **Proven enforcing:**
  an un-meshed plaintext `psql` got `server closed the connection` (sidecar reset pre-auth), while meshed
  clients work over mTLS (`pgvector ok`, `rag_chunks 439`). **qdrant/weaviate/neo4j stay PERMISSIVE by design**
  — their real traffic is *already* mTLS (both ends meshed); STRICT would only block un-meshed plaintext, not
  worth losing Prometheus metrics + NodePort admin in a single-user lab.
- **✅ Observability consolidated 2026-06-18.** (Was: Kiali on the addon Prometheus, a deliberate bring-up
  shortcut.) Now: a PodMonitor (`k8s/istio/podmonitor-istio.yaml`, labeled `release: monitoring` to match the
  stack's `podMonitorSelector`) + an istiod ServiceMonitor make the **kube-prometheus-stack scrape Envoy**
  (verified `count(istio_requests_total)=18`); Kiali's `external_services.prometheus.url` repointed at the
  stack; **the addon Prometheus dropped**; the **Istio Grafana dashboards** (mesh/service/workload/
  control-plane, IDs 7639/7636/7630/7645) imported into the existing Grafana (persisted on its PVC — optional
  later: ConfigMap-provision for IaC). Kiali also wired to **Jaeger** (`tracing.istio-system:16685`) **and
  Grafana** (`monitoring-grafana.monitoring:80`) — Mesh view all green.
- **Kiali security follow-up (2026-06-18):** the Istio addon ships demo-grade defaults. Hardened: `view_only_mode:
  true` (read-only) + ClusterRole read-only on Istio CRDs + non-placeholder signing key. **✅ Ingress auth DONE
  2026-06-18** — Traefik basicAuth Middleware `observability-auth` (`k8s/istio/observability-auth.yaml`, dev-password,
  secret created out-of-band) now fronts **both** `kiali.weyland.lab` and `jaeger.weyland.lab` (consistent with the
  other UIs). Kiali manifest tracked in `k8s/istio/kiali.yaml` (was untracked addon). **Residual (optional, deferred
  — defense-in-depth, not blocking in a single-user LAN lab):** a NetworkPolicy/AuthorizationPolicy + dropping the
  remaining workload `patch` verbs from the ClusterRole.

### B9 — Refactor Python scripts → Go binaries
Foreshadowed in weyland.md ("future Go CLI refactor"). Maintainability/distribution play;
not urgent. **Open:** which scripts? Go vs alternatives?

### B10 — Model registry
**MERGED with B16 — see B16 for MLflow detail.**

Central catalog + versioning + **internal distribution** of model artifacts (GGUFs, safetensors,
fine-tunes) so **rogueone (vLLM) + weyland (Ollama)** pull from internal storage instead of
re-downloading from the internet each time — and so fine-tunes get versions/metadata/lineage.
**Builds on B6 (MinIO = the artifact substrate)**; relates to B4 (eval/lineage) and any future
fine-tuning. **Options:** (a) simple MinIO-bucket convention (lightest); (b) an OCI registry
(Zot/Harbor) — Ollama models ARE OCI artifacts, and Ollama can pull from a private registry;
(c) MLflow Model Registry (MinIO+Postgres) if/when doing real fine-tuning + experiment tracking.
**Not urgent** — Ollama's local store + public pulls suffice while the lab is small. Revisit once
multiple hosts/models/fine-tunes make re-downloads and version-sprawl annoying.

### B11 — Whisper STT (speech→text) on weyland
**whisper.cpp** — Georgi Gerganov's C/C++ port of OpenAI's Whisper ASR, on the **same GGML library
as llama.cpp/Ollama**. Audio **in → text out**: transcription (+ timestamps, SRT/VTT subtitles),
non-English→English translation, ~99 languages, near-real-time mic streaming. **Runs
faster-than-real-time on the 9955HX CPU — no GPU** (models are small: `tiny` ~39M → `large-v3`
~1.5B, plus fast `large-v3-turbo`); STT is the *cheap* direction of audio (generation is the
GPU-hungry one — see Tentative). **Deploy:** a lightweight LXC on weyland (sibling to the Ollama
CT 102) running `whisper-server`, which exposes an OpenAI-compatible `/v1/audio/transcriptions`
endpoint → **voice-input front-end for the harness** (talk to OpenClaw/Hermes), meeting/voice-note
transcription, subtitle generation. **Open when scoping:** model size (accuracy vs speed), where
the endpoint sits behind Traefik, mic/streaming vs file-upload only. Pairs with the eGPU-gated
audio-*generation* item in Tentative (this is the input half you can have now for $0).

### B12 — API catalog / endpoint registry
**DROPPED — absorbed into B3 (IDP / Backstage).**

A single place to discover/register **every lab API** + interactive docs. **Distinct from the
gateway** (Traefik/APISIX *route* traffic; they don't *catalog* it). Lightweight first:
(a) Traefik clean hostnames for all services (`ollama`/`whisper`/`tools.weyland.lab` — pairs with
the CT DNS work); (b) **one aggregated Swagger/Redoc portal** pulling each service's
`/openapi.json` — FastAPI services (tool-server, whisper shim) already emit it; OpenAI-compatible
ones (Ollama, vLLM) use the standard spec; whisper-native `/inference` gets a stub. Live inventory
lives in **docs/api.md** (the manual precursor). **Defers to B3 (Backstage API catalog)** as the
heavyweight someday option. Trigger: endpoint sprawl makes "what's the URL again?" a recurring
annoyance (already starting — Ollama, whisper×2, tool-server, vLLM, 7 UIs).

### B13 — Open WebUI (browser voice/chat front door)
Self-hosted ChatGPT-style UI as the robust, browser-based consumer of the local models — the
payoff of **B7 (Ollama) + B11 (whisper)**. **Chat** ← Ollama (native integration); **voice input
(STT)** ← the whisper shim via Open WebUI's OpenAI-compatible Audio→STT setting
(`http://192.168.1.246:9000/v1` + dummy key); **TTS** optional later. Deploy on mother/k3s behind
Traefik → `chat.weyland.lab` (same pattern as the other UIs). **Why over OpenClaw for voice:** Open
WebUI's STT is a stable, documented setting and **fails *open*** (breaks one panel, not the agent)
— vs OpenClaw v2026.5.31's `tools.media.audio`, which is undocumented-for-version and **failed
closed** (took down the whole gateway; see [docs/runbooks/transcription-whisper.md](runbooks/transcription-whisper.md)).
**Additive — zero impact on OpenClaw/Telegram** (independent consumer of the same shared endpoints).
**Open when scoping:** auth (LAN/dev-password), persistence (PVC), which Ollama models to surface.

### B14 — Guardrails + Hermes read+act (learning track)
**✅ Status (2026-06-15) — DONE; both halves shipped in shadow.** The enforcement *promotions* below are
carved out as their own downstream items (B35 / B34 / B17+B19), not remaining B14 scope. The shadow-mode
guardrail pipeline is live at the tool-server seam: `input` hook (LLM Guard prompt-injection) + `output` hook
(LLM Guard toxicity, in-process NLI grounding `cross-encoder/nli-deberta-v3-small`) on `/context/*`; verdicts →
`/metrics` (Prometheus, ServiceMonitor wired) + `guardrail_verdicts` (Postgres). All `mode=shadow` (record-only,
never blocks); per-validator `off|shadow|flag|block` via `GUARDRAIL_MODE__*` env. **Read+act also shipped:** the
three action routes (`/pipeline/trigger`, `/evals/run`, `/evals/score`) are exposed on a separate `/mcp-act` MCP
mount, audited by the `act` hook (`policy.audit`, shadow) with the `actor` seam (trusted `X-Forwarded-Consumer`
header → `guardrail_verdicts.actor`, NULL until the gateway). Code: `services/weyland-tool-server/guardrails/`
(20 tests). Specs/plans: `aidlc-docs/construction/b14-guardrails-{design,plan}.md` + `b14-readact-{design,plan}.md`.
**Downstream promotions (separate items, not B14 scope):** (1) grounding threshold/method calibration before
`shadow→flag/block` → **B35**; (2) the enforcing act policy gate (allowlist/rate-limit/`block`) → built with
**B35**; (3) PII bake → **B34**; (4) gateway auth that injects the `actor` identity → **B17+B19** (handoff
documented there). The shadow plumbing for all of these is in place — they are promotions, not new infrastructure.

Runtime safety/validation of LLM I/O — **distinct from B4** (which measures quality *offline*). The
classic drivers (untrusted users, public exposure, compliance, brand safety) **barely apply to a
single-user LAN lab**, so this is **a learning + agent-prep track, not production hardening** —
don't over-build it. Worth-it slices even solo: (a) **grounding/faithfulness enforcement** —
flag/reject RAG answers unsupported by retrieved context (B4's Ragas faithfulness is the
*measurement* half; this is the runtime *block* on `/context/ask`); (b) **prompt-injection
awareness** — gets real once **B2 (Hermes/agents)** read untrusted content (Tavily/web results,
ingested docs). **Tools:** Llama Guard (Meta safety classifier — runs on *your* Ollama), LLM Guard
(input/output scanners: injection / PII / toxicity), Guardrails AI (structured-output validation for
agent tool-calls), NeMo Guardrails (programmable rails — heaviest). **Sequenced with B2.** Revisit
when agents process untrusted input, or for the learning.

**Read+act scope (added 2026-06-14):** B14 now also owns turning on Hermes's **write/act** path — the
tool-server's currently-untagged action routes (`/pipeline/trigger`, `/evals/run`, `/evals/score`)
exposed as MCP act-tools (B2 v1 deliberately excluded them, tagging only the 4 read tools). read+act was
previously *gated on* B14; it's now *part of* it, so the act-tools land **behind** the grounding/injection
checks above — not before them. This is the read-only-v1 → read+act step for the B2 agents (Hermes first,
OpenClaw same MCP URL).

### B15 — Local-model coding agents (opencode / Cline CLI)
Terminal/editor AI coding agents pointed at **weyland's Ollama `/v1`** — code with your *own* local
models, on-LAN; like Open WebUI (B13) but for coding. **opencode** (SST; open-source, model-agnostic,
Claude-Code-style TUI) and **Cline** (now has a CLI) both accept an OpenAI-compatible base URL, so
they drop onto `http://192.168.1.244:11434/v1`. Consumers of B7 — and the real payoff of B4's "best
coding model" finding (point them at `qwen3-coder:30b` / whatever wins). **Open when scoping:** which
agent(s), per-repo config, default model, auth. Low lift (client config, no new infra).

### B16 — MLflow (experiment tracking + model registry) — ✅ DONE 2026-06-19
**MERGED with B10 — this is the canonical MLflow detail section.** Live at `mlflow.weyland.lab` (dev-password): MLflow server (`k8s/mlflow/`), **Postgres** backend store (`mlflow` db/role), **MinIO** `mlflow` artifact bucket (proxied `--serve-artifacts`), meshed for STRICT Postgres, pg/s3 drivers pip-installed on start (no custom image). Smoke-tested end-to-end (run + param + metric + artifact → both stores).

System-of-record for **experiments + model artifacts**. Real value lands once the lab does
**fine-tuning**: track training runs (params/metrics/artifacts) and register/version the resulting
models with lineage. **Reuses MinIO** (artifact store) **+ Postgres** (backend store) — fits the
reuse ethos. **Pairs/overlaps with B10** (model registry): MLflow's Model Registry *could be* B10's
implementation, or complement it (B10 = serving-side distribution/OCI for Ollama/vLLM pulls; MLflow =
training/experiment lineage + registry). Also overlaps **B4**: MLflow could host eval-run tracking
with a standard UI — but we already built a lean Postgres `eval_*` store, so that's not the draw.
**Open:** MLflow vs (B10's) lighter MinIO-bucket / OCI-registry options.

### B17 — A2A (agent-to-agent protocol) evaluation
**MERGED with B19 — see the Mesh item.**

Evaluate **A2A (Agent2Agent)** — or similar (ACP, AGNTCY) — for the **agent↔agent edge only**. Born out of
B2 scoping (see docs/concepts/agent-platform-design.md §5). **Key framing: A2A is complementary to MCP, not a
replacement** — MCP = agent↔tools (the system view + acting on the system, *always*); A2A = agent↔agent
(discovery via Agent Cards, task lifecycle, streaming, long-running peer delegation). **Not needed for
read+act** — acting on the system is agent→tool (MCP) even when side-effecting. **A2A's actual trigger:**
**long-running, async, autonomous *cross-agent* delegation**, which becomes real as the agent fleet grows
powerful — **Hermes + OpenClaw + opencode/Cline (B15)**. **Sequenced with B15.** When evaluating: (a) check
native A2A support in each platform (cheap if shipped, heavy if we must adapter it); (b) confirm a real
peer-mesh need vs the cheaper MCP-tool bridge; (c) A2A would sit *alongside* MCP on one edge — nothing in the
MCP-based B2 build is wasted. **Default until then: MCP for everything, incl. the Hermes→OpenClaw bridge.**

### B18 — Spotify integration (Hermes tool)
Wire Hermes's `spotify` tool (playback / search / playlists / library) — **wanted: user has concrete use
cases** (CAPTURE them here — they drive scope + priority). Disabled in B2 v1 (off-theme for a system-view
agent, and setup-heavy). **Needs:** a Spotify *developer app* (client ID/secret), an **OAuth** flow to
maintain, and a **Premium** account for playback control; calls go **off-LAN** to Spotify's cloud (low
sensitivity — music control, not infra data). **Investigate:** Hermes's built-in `spotify` tool vs an MCP
server vs n8n; token/refresh handling in the CT (`~/.hermes/`, not committed). **Open:** the specific use
cases (TBD from user); which surface (Hermes tool vs MCP). One-line `hermes tools` enable once configured.

### B19 — MCP gateway evaluation
**MERGED with B17 — see the Mesh item.**

Evaluate a self-hosted **MCP gateway** (mcpx · MCPJungle · MCP Mesh · Local MCP Gateway · IBM ContextForge)
to **aggregate multiple MCP servers behind one governed endpoint** with auth/RBAC, audit logging, and
OpenTelemetry observability. Born from B2 scoping (docs/concepts/agent-platform-design.md §5). **Not needed now** —
at one MCP server (tool-server `/mcp`) + two agents there's nothing to aggregate; each agent registers the
one URL directly. **Becomes valuable when** the MCP mesh grows (more servers) AND we want centralized
auth/policy/observability over MCP traffic — pairs naturally with **B14 (guardrails)** + the cellular-seam
governance, and is a learning-track fit. **MCP stays the seam regardless**; a gateway *fronts* servers like
`/mcp`, it doesn't replace them. **Sequenced with B14/B17**, gated on the mesh actually growing.

#### Handoff from B14 read+act (audit slice) — seams already built for the gateway
The B14 read+act slice (`aidlc-docs/construction/b14-readact-design.md`) deliberately built the *boundaries*
for this gateway work and left the *enforcement* to it. When B19 starts, these are in place to front/consume —
don't rebuild them:
- **`/mcp-act` mount** (`weyland-tool-server/main.py`) — the action tools (`/pipeline/trigger`, `/evals/run`,
  `/evals/score`, tag `mcp-act`) are on a **separate MCP mount** from the read tools (`/mcp`). The gateway
  fronts **`/mcp-act` only** with auth/policy; `/mcp` (read) can stay open. The act surface is already an
  independently-addressable boundary — no need to split read/act here.
- **`actor` trusted-header convention** — `guardrail_verdicts.actor` (nullable column) is populated on every
  verdict from the **`X-Forwarded-Consumer`** header *only* (never a client-supplied claim), `NULL` today.
  The gateway authenticates the consumer and injects that header → verified identity flows into the existing
  audit rows with **zero tool-server change**. The trust boundary is already coded: the tool-server trusts the
  header because it will only accept `/mcp-act` traffic from the gateway.
- **Shadow `act` hook awaiting a policy validator** — `Hook.ACT` runs `policy.audit` (records only, never
  blocks; `weyland-tool-server/guardrails/`). The gateway's/this-work's job is the **enforcing** policy
  validator (allowlist of callable tools/jobs, rate-limit, `block`) — it drops into the existing per-hook
  validator chain (`guardrails/config.py`), no new plumbing. Built alongside **B35** (calibrate-and-enforce
  pass). Until then, `act` is audit-only.
- **Decision recorded:** no client-supplied identity is ever trusted (anti-spoofing). Identity is a
  gateway-asserted header or absent — this work must not loosen that.

### B20 — Home Assistant integration (Hermes tool)
Enable Hermes's `home_assistant` tool — extend the agent's "system view" from infra to the **physical
environment** (lights, sensors, switches). **Gated on two things, not GPU:** (1) a running Home Assistant
instance on the LAN (none yet) + a long-lived token; (2) it's an **act tool with physical side effects**, so
it belongs in the **read+act phase with B14 guardrails**, not read-only v1. Disabled in B2 v1. One-line
`hermes tools` enable once HA exists and guardrails are in.

### B21 — Agent media generation (image / video / TTS)
Enable Hermes's `image_generate`, `video_generate`, `text_to_speech` tools — **gated on the eGPU decision**
(see Tentative). All are diffusion / GPU-hungry and do **NOT** run on Ollama/CPU, so on the current CPU-only
box they'd be dead tools eating the agent's context. Disabled in B2 v1. Folds into the eGPU + audio-gen-GPU
items in Tentative (shared VRAM-diffusion need). `vision_analyze` (image *analysis*, not generation) stays
on (may run on CPU via `mistral-small3.2`). Re-evaluate when/if the eGPU lands.

### B22 — SearXNG (self-hosted search) — privacy-max
Optional replacement for **Tavily** (current search backend for OpenClaw + Hermes). Web search is inherently
off-LAN, but SearXNG removes the **cloud middleman**: queries go from your box straight to search engines —
self-hosted, free, no key. **Cost:** another service to run + rawer (non-agent-tuned) results vs Tavily's
clean search+extract. **Not urgent** — Tavily works fine indefinitely. Revisit if the Tavily middleman/quota
becomes a concern, or for privacy/learning. Both agents re-point at `SEARXNG_URL`.

### B23 — Break out arch.md component diagrams
`docs/arch.md` has grown into one large file carrying multiple Mermaid diagrams (full LAN topology,
per-CT subgraphs, the agent sequence diagrams) plus the host/endpoint tables — too large to scan or edit
comfortably. Split the diagram sections into their own files (e.g. `docs/diagrams/`), keep `arch.md` as the
narrative + an index linking out, and **validate each Mermaid block renders** after the move (content-
validation rule). **Near-term — sequenced right after B2.** Pairs with B25 (both reshape `docs/` IA); do the
diagram split as part of the same IA pass so B25's git-ingestion targets the final structure.

### B24 — Evaluate nerdctl
**nerdctl** = the Docker-compatible CLI for **containerd** (which k3s already runs). Today images are built
with `docker build` then shuttled in via `docker save | sudo k3s ctr images import -` (see the tool-server
deploy in docs/runbooks/agent-hermes.md). nerdctl can build **straight into k3s's containerd namespace**
(`nerdctl --namespace k8s.io build`), collapsing the save/import hop and dropping the Docker daemon from the
loop. **Evaluate:** does it simplify build→deploy without breaking the `imagePullPolicy: Never` local-image
pattern; rootless vs root on the k3s nodes; whether to keep Docker for dev ergonomics. Low-stakes tooling
eval; no infra commitment.

**DECISION (2026-06-15): DECLINE — keep docker.** The `docker build → docker save | k3s ctr images import`
flow is an **anti-corruption layer** between two bounded contexts (the build domain and the cluster's runtime
image store). nerdctl's sole real win is building **directly into k3s's live `k8s.io` store** — which
*collapses* that ACL, the opposite of what we want. The plumbing checks out (nerdctl
`--address=/run/k3s/containerd/containerd.sock --namespace=k8s.io`; our no-`FROM`-local-image Dockerfiles
sidestep the nerdctl #2550 local-base gotcha), so adoption is *feasible* — we decline on **architecture, not
capability**. Keeping docker *alongside* nerdctl would add daemons (dockerd + buildkitd), not reduce them.
Tax that sealed it: nerdctl also costs rootful `sudo` builds + a buildkitd daemon to learn + lost ecosystem
familiarity — none worth surrendering the build/runtime isolation. **No adoption.**

### B25 — Docs IA overhaul + RAG corpus expansion
**Absorbs U15** (git-based ingestion trigger — replaces inotify-on-Obsidian watcher with a Dagster git-pull
workflow targeting the full docs/ tree).

Three linked moves: **(1) Deprecate the Obsidian `weyland.md` note** — no longer useful as the primary
source; migrate ALL still-valid content into the appropriate `docs/` files so nothing is lost, then retire
it as a RAG source (today Dagster SFTPs that single file from rogueone — see U11). **(2) Restructure the
`docs/` information architecture** — organize the now-canonical docs into a coherent tree (pairs with B23's
diagram breakout). **(3) New Dagster ingestion workflow — pull all docs via git** — replace the single-file
SFTP pull with a job that clones/pulls the repo and ingests the whole `docs/` tree into the RAG, and broaden
the corpus beyond the one note. **Open:** repo/branch + cadence, doc chunking strategy, how the B23 diagram
files get ingested (or not), de-dup vs existing RAG content. **(4) ~~Resolve services inventory~~ → MOVED to
B28** — the `services`/`machines`/`models`/`memory_facts` tables (confirmed live 2026-06-15, no repo DDL) are
**OpenClaw's** out-of-band state, so disposition rides with the OpenClaw keep/retire decision. **Depends on B23**
(settle the IA/diagram split first so ingestion targets the final structure).

**Status:** **B25a DONE (2026-06-14/15)** — docs restructured into `concepts/runbooks/units/validation/diagrams`
+ root registries + README; all links fixed; Obsidian symlink retired; `concepts/data-schema.md` migrated and
**validated against live backends + eval-schema** (caught the missing `eval_*` tables and the 4 OpenClaw orphan
tables). The note was ~85% overlap/stale → discarded. **B25b** = ONE Dagster git-pull job ingesting **both
`docs/` AND `nodes/`** (markdown H2-chunking for docs + code-aware chunking for code), retiring the rogueone
watcher — **gated on B31** (audit the codebase before ingesting it; the repo is the RAG corpus). **[B31 audit]
Retire `nodes/rogueone/services/weyland-watcher/`** (`watcher.py` + `.service` unit + README) here, when B25b's
git-pull trigger replaces inotify — it's the live trigger until then.

### B26 — Hosted-model gateway (LiteLLM) + model catalog
✅ **DONE 2026-06-17.** Runbook: [docs/runbooks/model-gateway.md](runbooks/model-gateway.md).
Manifests `k8s/litellm/`; asset `model_catalog.py`; DDL `scripts/model-catalog-schema.sql`.

**Reframed from "Hermes Claude brain."** Original goal: give Hermes an on-demand stronger brain. Two roads
to Claude both rejected: (1) **Anthropic API key** = metered, declined; (2) **Claude Pro/Max subscription via
a proxy** = ToS gray area (subscription is licensed for use *inside* Anthropic's products; Anthropic has
broken tools that proxy its OAuth). "Connect Claude Code" isn't a road — Claude Code is a *client*, not a
model endpoint. **Claude-in-lab = you driving Claude Code** (B29, already MCP-wired); Hermes stays local.

**What shipped instead** — the LiteLLM gateway that was always on the roadmap ("→ LiteLLM (future)" in
requirements-analysis.md), pointed at **API-key** providers (no ToS issue, free tiers = $0):
- **LiteLLM** on mother/k3s (`mother:30400/v1`, `litellm.weyland.lab`), **wildcard routing** → every
  **Gemini + OpenRouter** model behind one OpenAI-compatible endpoint; Bearer = `LITELLM_MASTER_KEY`.
- **Governed egress:** off-box **cut-off valve** (`valve.sh` — scale to 0; agent can't reach it),
  `LiteLLMEgressEnabled` + spend Telegram alerts (B5 Alertmanager), `/metrics` scraped.
- **`model_catalog`** Postgres table — Dagster asset (6h, `weyland_catalog_schedule`) pulls
  OpenRouter + Gemini + Ollama, **replace-by-source**; first run: openrouter 336 (26 free) / gemini 37 /
  ollama 6. The guess-free registry of reachable models (the B12-ish model catalog, made real).
- **Hermes auxiliary lanes pinned local** (safety, was the actual auto-off-LAN hole): `title_generation`,
  `web_extract`, `compression`, `skills_hub`, `approval` → local Ollama (`vision` left, needs a vision model).

**Remaining/optional:** wire a Hermes `custom` provider at the gateway for on-demand escalation (`/model
--provider`, default stays local); render a `docs/models.md` view from `model_catalog` if eyeballing is wanted.

### B27 — Enable Hermes Kanban skills
**Design (finalized 2026-06-17): `aidlc-docs/construction/b27-kanban-design.md`** — scope (a) self-management
+ (b) roadmap co-pilot. **Board = Hermes's native durable SQLite Kanban** (built in, no container, no Postgres —
richer than anything we'd build: deps, workers-in-isolated-workspaces, dispatcher, swarm, decompose/specify).
**Planning brain = Gemini free** (`gemini-flash`) via the gateway, pinned to `auxiliary.kanban_decomposer` +
`triage_specifier` only; default brain + workers stay local `qwen3-coder`. **$0, no paid models.**
**`backlog.md` → `docs/`** (step 1) feeds the RAG + the one-way roadmap-sync script. Plan-only → autonomous.
Turn on Hermes's built-in **Kanban** skills — the agent's native task/board/goal-management scaffolding (part
of the base framework prompt; see docs/runbooks/agent-hermes.md) — so Hermes can **decompose, plan, and track
multi-step work on its own board** instead of one-shot turns. **Sequenced right after B26 (Claude) by
design:** autonomous multi-step Kanban planning leans on a stronger brain, so it pays off most once Claude is
available for the planning turns (local `qwen3-coder` can still drive it, just less reliably). **Possible
payoff:** point the Kanban at the **weyland roadmap itself** (this backlog) — agent-assisted grooming /
execution tracking. **Open:** scope (the agent's own task planning vs managing our roadmap); board
persistence; which brain runs planning turns; read-only vs act (if the board drives real changes, that ties
to B14 read+act + guardrails).

### B28 — OpenClaw rehabilitation (deprioritized — much later)
Decision 2026-06-14: OpenClaw is **shelved, not deleted** — a powerful lab toy that's currently more pain than
payoff. This item is the future cleanup to make it usable again, done **only when there's appetite** (nothing
depends on it; Hermes carries the agent role). Captured degradation from `openclaw doctor` (2026-06-14) so it
isn't lost:
- **weyland MCP not surfacing to the brain** — registered + probes 4 tools at the CLI, but the agent's tool
  list is empty (gateway MCP runtime stuck "reconnecting"); a container restart didn't clear it.
- **No command owner** (`commands.ownerAllowFrom` unset) → owner-only / privileged actions + exec approvals
  can't run; the agent can't self-fix.
- **Brain auth expiring** — `anthropic:claude-cli` ~8h to expiry; needs re-auth.
- **Memory search broken** — provider `openai` with no key → semantic recall dead (set key, switch, or disable).
- **Tool allowlist too narrow** — agent `main` can't even use the `message` tool (likely also gating MCP tools).
- **Security** (lab/LAN, low urgency): plaintext secrets in `openclaw.json` (telegram token, tavily key,
  gateway token); gateway bound `0.0.0.0`.
- **Operability:** reachable only through the gateway Docker container (`docker exec …`) — painful.
**Two decisions to make when we reach it: (1) keep vs retire? (2) if keep, refactor vs rewrite?**
**When revisited:** answer (1) first — whether OpenClaw's unique value (plugin/channel breadth) is still wanted
vs just retiring it; then (2) refactor the existing degraded gateway vs a clean rewrite. If kept, fix roughly
in order: owner → MCP surfacing → auth → memory → secrets.
- **Out-of-band Postgres tables (moved here from B25):** OpenClaw created `services`, `machines`, `models`,
  `memory_facts` in the shared `weyland` DB (confirmed live 2026-06-15; no repo DDL; nothing else reads them).
  Reconcile or drop them as part of the keep/retire decision. See `docs/concepts/data-schema.md` §5.
- **OpenClaw helper scripts (deferred here from the B31 codebase audit):** `nodes/openclaw/bin/` —
  `read-weyland-note` (SSH-cats the now-retired Obsidian note), `weyland-context` (RAG-search CLI),
  `ask-rogueone-vllm` (→ rogueone vLLM), `weyland-db` (psql wrapper with `services/machines/models/chunks`
  shortcuts — ties the out-of-band inventory to OpenClaw tooling). Left intact for now; retire or redo with the
  keep/retire call.

Its prior "both agents" roles (B14 read+act, B18 Spotify, B20 HA, B21 media-gen, B22 SearXNG) are Hermes-now
until this lands. See [[openclaw-deprioritized]].

### B30 — Real-time docs ingestion trigger (Extras / Optimization)
Self-hosted **GitHub Actions runner on the LAN** fires the Dagster `launchRun` mutation on push — NAT-free
near-real-time ingestion without exposing mother. Deferred: the 15-min cron + hash-gate is fine until that
latency actually bothers us. The trigger contract (`launchRun` to the Dagster GraphQL endpoint) is unchanged from B25b, so
this bolts on with zero rework.

### B32 — NeMo Guardrails evaluation (Extras / Optimization)
**NeMo Guardrails** (NVIDIA) — a *programmable* guardrails framework: rails authored in the **Colang** DSL
(topical rails = keep on-topic; dialog-flow rails = allowed conversation paths; jailbreak / fact-check rails),
wrapping the LLM as a conversational control layer. **Deferred from B14** because it's the heaviest option (a
whole framework + a new language) and built for **dialog management**, not the request/response **I/O scanning**
B14's tool-server pipeline does (Llama Guard + LLM Guard + grounding judge cover that). **Where it might fit:**
the **Layer-2 agent layer** (Hermes) for dialog/topical rails — evaluate then. Not the tool-server seam.

### B34 — Evaluate + bake PII guard (Maturity / Hardening / Polish)
B14 shipped the **PII validator coded but unbaked**: the `PIIValidator` (llm_guard `Sensitive` → presidio
+ spaCy) exists in `guardrails/validators/llm_guard.py` and its config line is present-but-commented in
`guardrails/config.py`, but the presidio/spaCy model is **not baked into the tool-server image** (Option A at
build time — the heaviest, lowest-signal-in-this-corpus guard was deferred to keep the image lean and the
airgap-offline guarantee clean). **B34 promotes it:** (1) **eval** — using the shadow telemetry already
flowing for injection/toxicity/grounding, confirm PII detection carries real signal on *this* corpus (own
infra docs: hostnames/IPs/secrets) rather than near-constant PASS noise; a **multi-user / answer-export**
trigger also promotes it regardless. (2) **bake** — add presidio + a spaCy model (`en_core_web_sm` to stay
lean, or `_lg` for accuracy) to the Dockerfile *before* the `HF_HUB_OFFLINE` lines, mirroring the injection/
toxicity/NLI bakes. (3) **enable** — uncomment the `llm_guard.pii` line in `config.py` (ships `Mode.SHADOW`).
The resilient per-validator loader means it lights up with zero other code changes. **Depends on:** B14 shadow
data accumulated. **Effort:** small (build + config), modulo presidio/spaCy bake fragility.

### B35 — Grounding guard calibration (Maturity / Hardening / Polish)
B14's grounding validator (`grounding.nli`, `guardrails/validators/grounding.py`) emits `max_entailment` ∈ [0,1]
and FLAGs below a **guessed `0.5` threshold** — set before any data existed. First live run already FLAGged a
*correct* "the context doesn't cover that" answer at `0.295`, i.e. the threshold is uncalibrated and the
whole-answer-vs-single-chunk NLI method systematically under-scores answers synthesized across multiple chunks.
**B35 calibrates it:** (1) **collect** — let shadow mode accumulate `max_entailment` across many real
`/context/ask` queries in `guardrail_verdicts` (happening now). (2) **label** — judge a sample (hand or
stronger model) as truly grounded vs hallucinated. (3) **separate** — plot the two score distributions; set the
threshold that best splits them (max F1, or bound the false-flag rate). (4) **fix method if needed** — if no
threshold separates them, switch from whole-answer-vs-chunk to **sentence-level entailment** (score each
answer-sentence vs its best chunk, aggregate) or **concatenate top-k chunks into one premise**. This is the
**prerequisite to ever moving grounding from `shadow` → `flag`/`block`** — enforcing on a guessed threshold
would block good answers or pass hallucinations. Ties into the B4 eval harness (reuse its judge-panel pattern
for labeling) and feeds the B1 model-eval data product. **Depends on:** B14 shadow data. **Effort:** small-medium
(analysis + a possible scoring-method swap).

### B36 — Hermes dashboard performance (Maturity / Hardening / Polish)
**Context — deployed 2026-06-17 (ad-hoc, out of roadmap order).** The native Hermes web dashboard (config /
sessions / **Kanban** view) is live: web UI **built on rogueone** (the pip install shipped source only, with
devDeps omitted → built there, `web_dist` shipped to CT 104), served localhost-only by a systemd unit
(`hermes-dashboard`, `127.0.0.1:9119`), fronted by **nginx on CT 104** with TLS (wildcard cert) + an **IP
allowlist** (rogueone only — basic-auth storm-prompted against the SPA's XHR/websockets, so it was dropped).
DNS: `dashboard.weyland.lab` → CT 104 (CoreDNS block + rogueone `/etc/hosts`). Files:
`nodes/weyland/hermes/{hermes-dashboard.service,dashboard-nginx.conf}`.
**The problem:** it **works but is dog-slow.** Suspects to investigate: the dashboard backend on the
4 vCPU / 6 GB CT 104; likely live polling / heavy SPA; possibly the extra proxy hop. **When revisited:**
profile what it's doing (network tab + CT load), consider bumping CT resources, disabling polling, or caching;
decide whether it's worth keeping vs the CLI/Telegram board views. **Docs still owed** (deferred to keep
momentum on the roadmap): a runbook (`docs/runbooks/`) + `dashboard.weyland.lab` in `api.md`/`hosts.md`/arch —
fold into this item.

### B33 — Co-resident / warm-parallel model serving (Hardware-Gated)
The latency-free way to run a guard (or any second model) alongside the main one is to keep **both resident** —
`OLLAMA_MAX_LOADED_MODELS=N` + `KEEP_ALIVE=-1` (requests route to the right warm model; nothing cold-starts).
Surfaced from B14's grounding-guard venue discussion. **Gated on hardware:** CT 102's ~48 GB cgroup is already
near-full with one 30B-A3B at 64K, so a *second large* model can't co-reside today — this unlocks with RAM
headroom (the "weyland box" decision) or the eGPU (VRAM). Note: *small* guard models can already co-reside or
run in a dedicated guard CT / in-process (that's B14's feasible path) — **B33 is specifically the
keep-big-models-warm-in-parallel capability.** Related: the vLLM **multi-LoRA** hot-swap path (cheap adapter
swap on a shared warm base) if guards are ever LoRAs of the base model.

### B31 — Codebase audit / restructure (`nodes/`)
**The repo is the RAG corpus** — "ingest everything we check in" means `nodes/` (code + k8s manifests) gets
ingested too, so it must be as clean and relevant as the docs were before B25b. **Garbage in the repo = garbage
in the RAG.** This is the **code analog of B25a**, and a **prerequisite for B25b's ingestion**:
- **Audit `nodes/` for relevance:** retire dead/stale scripts, bootstrap/one-off helpers, abandoned
  experiments, and the now-obsolete rogueone watcher (U15).
- **Audit for structure:** organize what stays so ingestion targets a coherent tree.
- *(Ingestion mechanics — code-aware chunking, tracked-file selection, the `bge`-on-code caveat — live in
  **B25b**, the unified docs+code job, not here. `.gitignore` already excludes node_modules / the openclaw
  clone / aidlc-docs / CLAUDE.md.)*

**Sequence: B31 (this) → B25b** (one Dagster job ingesting the cleaned `docs/` + `nodes/`). Ties into data mesh
(code/config as a Data-as-a-Product).

**Status (2026-06-15): audit DONE — codebase is clean.** Retired the 2 dead bootstrap RAG scripts
(`mother/bin/embed-weyland-chunks`, `ingest-weyland-note`). **Security:** `k8s/n8n/encryption-key.txt` is a
stray committed secret (n8n reads from a k8s Secret, not the file) → gitignored; **untrack + rotate the key is
a security task for the user** (already in git history). Corrected 2 false-positives: kept
`weyland-dagster-base/Dockerfile` (used by dagster webserver/daemon as `weyland-dagster-base:local`) and
`telegram-test-rule.yaml` (documented test fixture in observability.md). Deferred: OpenClaw `nodes/openclaw/bin/*`
→ B28, `weyland-watcher` → B25b. No structural reorg needed — the `nodes/<host>/…` layout is coherent.

### B29 — Connect Claude Code to the weyland system-view MCP
Make this Claude Code session a first-class **consumer of the weyland system-view MCP**
(`http://192.168.1.243:30080/mcp`) — the same URL Hermes uses — so I understand the **live system**
(`status` / `list_models` + RAG via `context_ask` / `context_search`) directly and deterministically, instead
of relying on stale git. **MCP, not A2A:** connect to the tool *server*, not to an agent (no lossy LLM
middleman; matches the B17 framing). Claude Code speaks MCP natively (`.mcp.json` / `claude mcp add`,
streamable-http transport). **Immediate directive** alongside B25 — and the RAG half scales with B25 (better
ingested corpus → more useful `context_ask`). Re-confirms the Hermes↔MCP path from a second client. **Open:**
`30080` reachability from the dev host; read-only now (act later, gated like B14); whether to scope which
tools load.

### U13 — sentence-transformers image slimming
- **Running-list item**: 12
- **Theme**: B — footprint
- **Scope**: Reduce or split the heavy sentence-transformers Docker image.

### U14 — n8n workflow export to git
- **Running-list item**: 13
- **Theme**: D — config-in-git
- **Scope**: Export the n8n workflow(s) into git now that the structure has stabilized.

### U16 — Weaviate UI (React frontend)
- **Running-list item**: 15
- **Theme**: F — deferred
- **Scope**: Custom React frontend for Weaviate schema browsing, object inspection, and
  search against the self-hosted instance.
- **Note**: Referenced as "U6" in older docs (weyland.md / aidlc-state.md); renumbered
  to U16 under priority order.

### U17 — Migrate platform API routes APISIX→Traefik; APISIX→outliers-only
**DROPPED — stale; U17 removed from priority list.**

- **Origin**: U9 follow-up (cellular architecture, deferred from U9 scope a)
- **Theme**: architecture / E
- **Scope**: Move APISIX's existing platform-API routes (`/context`, `/pipeline` →
  weyland-tool-server) onto Traefik (the platform front door). Repurpose APISIX to front
  only the outlier cell (non-k8s assets). Cross-cell path becomes APISIX → Traefik →
  service (the anti-corruption seam). Requires the non-k8s asset inventory.
- **Priority**: after U9; user may reprioritize. NOT yet in the numbered running list
  (which tracks the original 15 items) — added as an architecture-driven follow-up.

### B64 — Diagram tooling: migrate docs diagrams off Mermaid (Polish — AFTER B1 data mesh)
**Added 2026-06-25.** Mermaid's autolayout cramps + crosses edges past ~10 nodes and renders too small (no real zoom) — the `c4-component-mother` diagram is unreadable. Migrate to a better code-as-diagram tool with scalable SVG output.
- **Options** (all free / self-hostable / code-in-repo): **D2** (recommended — far better autolayout via ELK/dagre, clean scalable SVG, MkDocs plugin, free layouts; no paid TALA needed) · **Structurizr** (purpose-built C4 — define the model once → auto-generate layered context/container/component views, structurally kills the "one giant diagram" problem) · **PlantUML + C4-PlantUML** (mature, C4 macros, SVG). Optional infra: **Kroki** (one self-hosted render service for all of them → embed SVG in MkDocs; fits the lab's self-host pattern).
- **Also**: split the overloaded `c4-component-mother` into focused views (data/RAG plane · platform+auth · data-mesh · mesh/observability) — a better renderer alone won't fix one 22-component diagram.
- **Sequencing**: AFTER B1 (data mesh). Keep Mermaid fresh + accurate until then (content over polish). Pilot D2 on `component-mother` first to compare before committing.

### B65 — DataHub catalog integration: the datastore set in 3 tiers (B1.3 — repurposed from the candidate list)
**Restructured 2026-06-25.** B65 is now the **datastore-integration tracker** for the B1.3 "catalog every source" work (moved under B1, in progress). Every datastore sorted into 3 tiers.

**Tier 1 — HAVE → integrate now** (already running; just catalog via DataHub connectors):
**Dagster ✅** (custom emitter) · **Grafana ✅** (recipe codified, SA token via DataHub Secret → B69) · **Iceberg/Nessie ✅** (+ Dagster→Iceberg lineage) · **MLflow ✅** (+ eval→MLflow tracking, `eval_mlflow_log` → `weyland_rag_eval`) · **Neo4j ✅** (graph schema via apoc) · **Postgres ✅** (ALL DBs, `weyland` superuser, profiling on) · Kafka · **S3/MinIO ✅** (B72 custom-emit) · **Qdrant ✅** · **Weaviate ✅** (custom emit via `datahub_emit.py` emit_qdrant/emit_weaviate, lineage ← `*_write`; native connectors give no pipeline lineage / none for Weaviate) · **OpenSearch ✅** (own playground — populated with the BM25 lexical index `weyland_chunks` (775), custom emit `emit_opensearch`; hybrid *use* → [B74]; DataGrip can't talk to OS 3.7 → dim-6 = Dashboards Dev Tools) · **lakeFS ✅** (write-through dataset versioning on `music` repo, custom emit `emit_lakefs` lineage ← `datasets_commit`). _(CSV moved out → [B68].)_ Recipes + emitters in `k8s/data-mesh/datahub-ingestion/` + `datahub_emit.py`. **11 of 12 done (2026-06-27); remaining HAVE: Kafka — deferred, needs the real streaming build (not a catalog-only freebie).**
_(Low-catalog-value / optional: Valkey-Redis cache; Prometheus/Loki/Tempo — observability stores surfaced via Grafana, not typical catalog targets.)_

**REUSABLE PATTERN for gated/SSO Tier-1 sources (from Grafana, 2026-06-26):** every browser UI is forward-auth gated, so a DataHub UI pull connector must (a) point at the **in-cluster service URL** (`http://<svc>.<ns>.svc.cluster.local:<port>`), NOT the `*.weyland.lab` ingress (that bounces the API call to Keycloak → 401), and (b) authenticate with a **service-specific token**. Where SSO-mapped roles can't mint that token in the UI (e.g. a non-admin Grafana role hides Service Accounts), **mint it via the service's admin API using its admin secret** — Grafana: `kubectl get secret grafana-admin` (keys `admin-user`/`admin-password`) → `POST /api/serviceaccounts` (role Admin) → `POST /api/serviceaccounts/{id}/tokens` from an in-cluster curl pod. The DataHub executor is meshed/PERMISSIVE so it reaches in-cluster services; for STRICT-mTLS targets (Postgres) the meshed executor still connects. Expect this for MLflow / Nessie / lakeFS / etc.

**Tier 2 — IMPLEMENT → integrate now** (committed in the B1 design; stand up, then catalog):
**Trino ✅** (1st Tier-2 done, 2026-06-27 — single-node, native-Nessie catalog + postgres; in DataHub w/ sibling/upstream lineage to iceberg; full gate closed; [runbooks/trino.md](runbooks/trino.md)) · **DuckDB ✅** (2nd Tier-2 done, 2026-06-27 — served via **GizmoSQL** Arrow Flight SQL (DuckDB JDBC is embedded-only → no host:port); in-memory DuckDB w/ views over the lakeFS Parquet; IDEA via Arrow Flight SQL JDBC + `emit_duckdb` catalog (platform `duckdb`, lineage ← parquet); **meshed plaintext + Istio mTLS** (resolved the TLS_SKIP_VERIFY finding); gate closed incl. `GizmosqlDown` rule + runbook; **gRPC-TLS ingress for external IDEA = B69**; [runbooks/gizmosql.md](runbooks/gizmosql.md)) · **Superset ✅** (3rd Tier-2 done, 2026-06-28 — Helm 0.17.2/Superset 6.1.0; Keycloak OIDC; shared Valkey cache; Trino + 11 Postgres DBs connected; 48 datasets + 15 charts + "Weyland Platform Overview" dashboard; in DataHub via native superset source; `SupersetDown`+`SupersetWorkerDown` PrometheusRules; [runbooks/superset.md](runbooks/superset.md). Gotchas: psycopg2 bootstrap install via system pip `--target` into venv site-packages; data-mesh ns needs `istio-injection=enabled` label for STRICT mTLS Postgres; mkcert CA bundle for Keycloak back-channel; `SUPERSET_SECRET_KEY` in `extraSecretEnv`; Argo `terminate-op` pattern for stuck syncs.) · **TimescaleDB ✅** (4th Tier-2 done, 2026-06-28 — `timescale/timescaledb-ha:pg16`, ns `data-mesh`; 5 hypertables (eval_scores_ts, guardrail_verdicts_ts, dagster_run_durations, unleash_feature_metrics, datahub_ingestion_runs); hourly Dagster feed (`weyland_timeseries_job`); DataHub `emit_timescaledb`; Superset 10 charts; Grafana datasource; `TimescaleDBDown` PrometheusRule; [runbooks/timescaledb.md](runbooks/timescaledb.md). Gotchas: DataHub GraphQL `lastExecRequest` → `executions.executionRequests`; GraphQL only reachable in-cluster; `max_connections=200`.) · dbt Core · Flink (B1.5) · ClickHouse · Cassandra · CockroachDB · MySQL/MariaDB · MongoDB · Feast (B1.8). _(Kafka pairs here w/ Flink.)_
_(KEDA on-demand for the heavy/occasional ones per the run-mode tiers.)_

**Tier 3 — KEEPERS → re-eval AFTER Tiers 1+2, BEFORE any resource change** (the additive / zero-local-cost keeps from the candidate cull):
Doris (OLAP variety, on-demand) · Spark (big-data compute, on-demand) · RDF/triplestore (semantic-web, lightweight) · Okta · BigQuery · DynamoDB (cloud SaaS — zero local cost). Dropped candidates → [B67].

**Sequencing gate (the point of the tiers):** do Tier 1 + Tier 2 → **measure the actual always-on / on-demand RAM footprint** → THEN re-evaluate Tier 3 keepers AND size the mother vCPU/RAM resize to the *real* numbers. **No resource changes before that measurement** (proposed targets in chat: mother 44/16, ollama 32/8, OpenClaw kept 6/2 — but confirm against measured footprint).

**✅ Dagster (Tier 1) — DONE via custom emitter (2026-06-26).** 17 datasets + lineage in DataHub (15 original + the 2 iceberg_export assets).
- **Why not the standard paths (both dead on Dagster 1.13.10):** OpenLineage-dagster supports ≤1.6.9 (removed 2025). The acryl-datahub-dagster-plugin's `datahub_sensor` is built on Dagster's `run_status_sensor`, **broken since 1.7.3** ([dagster#21526](https://github.com/dagster-io/dagster/issues/21526), overwhelm + cursor-fix removed [dagster#19224](https://github.com/dagster-io/dagster/issues/19224)): daemon logs `Checking for new runs… skipped` every tick even at zero run volume → indices stay 0. Not fixable by config.
- **What works:** `weyland_pipeline/datahub_emit.py` — walks `all_assets`, emits per asset a Dataset (name + **description** + `dagster_group` custom-prop) + a **group tag** + UpstreamLineage, to GMS via the `datahub` REST SDK. Wired as `datahub_catalog_emit_job` (op) + hourly `ScheduleDefinition`. `requirements.txt`: dropped the plugin → plain `acryl-datahub`. Sensor + its imports removed from `definitions.py`. Idempotent (DataHub upserts). Baked + schedule-safe (39 MCPs: 15 props + 15 tags + 9 lineage).
- **Enrichment DONE (2026-06-26):** descriptions (14/15 assets have one — `model_catalog` doesn't) + group as prop+tag. **No column schema** — confirmed the assets carry no `TableSchema` metadata (they're non-tabular: embeddings, vector/graph writes), so there's nothing to map; the schema tab stays empty by nature, not omission.
- **Bring-up gotchas (cost the bulk of the session):** (1) GMS metadata-auth needs a DataHub PAT → `datahub-token` secret in the weyland ns. (2) **Long-JWT paste-mangling** on the secret's command line → use `read -rs` not `--from-literal='<paste>'` ([[feedback-verify-secret-after-create]]). (3) **The real blocker: `DATAHUB_GMS_TOKEN` env was `len=0`** — we added it to `user-code.yaml` but never pushed, and the dagster Argo app's **selfHeal stripped the manually-applied env back to git state**. Fix = push the manifest, never `kubectl apply` ([[feedback-remind-to-push]] / [[argocd-gitops-gotchas]]). (4) Deploy = manual `docker build` + `k3s ctr import` (`:local`/`Never`, no registry until B57) — Argo can't deploy image contents, only manifests.

### B66 — Operator Agent Platform (consolidation — supersedes 13 fragmented agent items)
**Added 2026-06-25.** Folds the scattered Hermes/OpenClaw work into ONE effort: a **Claude-brained, multi-ingress operator agent**. **Thesis:** the agents' real value is *remote/mobile ingress that acts on the lab* (text it from anywhere → it acts); the failure is the **brain** — Hermes on weak free/local models is slow/unhelpful, OpenClaw "feels" better. Fix = give the agent a **Claude brain via the $0 subscription-headless path** (`claude -p` / Agent SDK with the Max-subscription auth — NOT the paid Claude API, which is exactly why the Claude-brain path was *declined* at B26). Keep the existing ingress + act (`/mcp-act`) + tool plumbing.
- **Workstreams (each absorbs an old item):**
  - **Brain** — Claude via subscription-headless ($0); revisits the B26-declined decision with the new path.
  - **Base agent** — pick **Hermes vs OpenClaw** as the gateway (**resolves B28**): Hermes = blessed/stable but slow; OpenClaw = fast/responsive but deprioritized/fragile. Decide reuse-OpenClaw-responsiveness vs Hermes-base at build time; **do NOT decommission OpenClaw until decided** (now a reuse candidate, not an auto-retire).
  - **Ingress** — Telegram (live) + other channels (Whisper voice, web).
  - **Act + incident** — act tools (`/mcp-act`, live) + **B45** (agent enriches/acts on incidents, off the critical alert path).
  - **Tools** — **B20** (Home Assistant), **B18** (Spotify), **B21** (media-gen).
  - **Guardrails** — **B32** (NeMo dialog/topical rails for the agent layer).
  - **Mesh / delegation** — **B17+B19** (A2A + MCP gateway), **B15** (local coding agents Hermes delegates to).
  - **Ops** — **B36** (dashboard perf), **B52** (Hermes error tracking).
- **Split into two efforts (2026-06-25, mirrors Linear):** **B66 = core** (brain, base agent, ingress, act, mesh — keeps B15, B17+B19, B20, B36, B28) · **"Operator Agent Platform (Enhancements)"** (Linear EMA-56, sibling, Low) = the agent extras **B18** (Spotify), **B32** (NeMo dialog rails), **B45** (incident-response), **B52** (error tracking).
- **Done base (context, not re-scoped):** B2 (platform), B26 (LiteLLM brain), B27 (kanban).
- **Resource note:** OpenClaw's 8 GB/4 CPU retirement (floated in the reallocation plan) is now **contingent on the base-agent decision** — if OpenClaw is reused, it stays.
- **Sequencing:** its own design (brainstorm) when reached; orthogonal to the data mesh. Big-rock effort.

### B67 — Dropped datastore candidates (Extras — re-evaluate later)
**Added 2026-06-25.** Cut from the B1.3 "ingest every source" connector pass as **redundant with the table-stakes WILL-DO set** (not for lack of merit). KEDA solves the *resource* cost of redundancy but not the maintenance / catalog-clutter / learning-overlap, so these were dropped on purpose. Parked to re-evaluate if a concrete need emerges.
- **Druid** — real-time OLAP, but the **heaviest** on the list (coordinator + overlord + broker + historical + middlemanager + ZooKeeper + deep storage + metadata DB) and pure overlap with **ClickHouse** (committed). Worst ROI.
- **Vertica** — redundant OLAP; community edition capped (1 TB / 3 nodes) + enterprise baggage.
- **Dremio** — overlaps **Trino** (federation) + **Cube** (semantic); its edge (reflections/acceleration) doesn't justify a second federation engine. **The closest "keep" call — reprieve this first if any get reconsidered.**
- **Airbyte** — overlaps **dlt + Debezium** (committed EL/CDC); heavy (server + workers + Temporal + Postgres + UI); its 300-connector catalog only matters for external-SaaS pulls (rare on a LAN lab).
- **Airflow** — pure duplicate of **Dagster** (the committed orchestrator).
- **Metabase** — overlaps **Superset + Lightdash** (committed BI); the design already said "No Metabase."
- **Re-eval trigger:** a concrete need the committed stack can't meet (real-time-OLAP gap ClickHouse/Doris don't fill → Druid/Vertica; an external-SaaS EL need → Airbyte; a Trino-acceleration gap → Dremio). KEPT instead (additive/new capability or zero-local-cost SaaS): Doris, Spark, RDF, Okta, BigQuery, DynamoDB.

### B68 — CSV / Google Sheets ingestion (DataHub) — Maturity / Polish
**Added 2026-06-25.** Deferred from B65 Tier 1 to the **Maturity / Polish** tier (between Core and Extras). **BLOCKED:** find suitable spreadsheets in Google Drive first. Two paths, decided once the sheets are picked:
- **csv-enricher** — bulk-**enrich** existing entities with metadata (`tags`/`glossary_terms`/`owners`/`ownership_type`/`description`/`domain`/`subresource` for column-level/`classification`), keyed by `resource` = entity URN; arrays `|`-delimited; `write_semantics` PATCH (append) vs OVERRIDE. **Requires entities already ingested** (B65 Tier 1 sources) so there's something to enrich.
- **File/S3 source** — **catalog** the CSV rows as a *dataset*: export Sheet → CSV → MinIO → DataHub S3 source infers the schema.
- Doc: https://docs.datahub.com/docs/generated/ingestion/sources/csv-enricher

### B73 — Find/build uses for the datasets-lake formats (Maturity / Polish)
**Added 2026-06-26.** B72 produced the music data (Spotify audio features + FMA metadata) in **five formats** (Parquet · Lance · Avro · Arrow · Iceberg) + raw CSV — but they're currently **inert** silver/gold artifacts sitting in MinIO + the catalog. Build a **real use case per format** that exercises its specific strength, so each earns its keep and the format choices are validated *by use*, not just by the rationale in [datasets-lake.md](runbooks/datasets-lake.md):
- **Parquet** → analytics queries via **Trino / DuckDB** (Tier-2) — genre/feature aggregations over the Spotify set.
- **Lance** → **vector / similarity search** (LanceDB) — music recommendation / nearest-neighbour over the audio-feature vectors (ties to **Stud.IO** + the Spotify Hermes tool [B18]).
- **Avro** → **stream through Kafka** (producer → consumer) — the row/schema-evolution format in motion.
- **Arrow** → **zero-copy load** into polars/pandas for fast EDA — prove the IPC/transport story.
- **Iceberg** → **time-travel / schema-evolution / ACID** demo via Trino — the gold-table capabilities.
- **Goal:** each format demonstrated by a concrete workload, not left as a catalog entry. **Sequence after** the relevant Tier-2 engines exist (Trino/DuckDB, Kafka) — those are prerequisites for several of these.

### B74 — Hybrid retrieval (BM25 + dense fusion) in the tool-server
**Added 2026-06-27.** The **value-realization of the OpenSearch BM25 work** (B65). OpenSearch now holds the corpus as a lexical index (`weyland_chunks`, 775 chunks, kept in sync by `opensearch_write`), but the tool-server RAG still queries **only the dense/vector path** — so the sparse half is built and cataloged but **not yet used at query time**. Build it:
- **Retrieve from both** — run the query against **BM25** (OpenSearch `weyland_chunks`) and a **dense** backend (pgvector/Qdrant), then **fuse** the two result sets — **Reciprocal Rank Fusion (RRF)** is the simplest robust default (no score-normalization headaches); weighted-sum is the alt.
- **Where:** the retrieval path in `weyland-tool-server` (`/context/ask` + the RAG context builder). Keep fusion **configurable** (toggle + weights/k) so dense-only stays available for comparison.
- **Why it pays here specifically:** the corpus is **code + config + docs + the aidlc-kb** — dense embeddings are weak on exact identifiers (config keys, flags, error codes, file paths, commands) that BM25 nails; fusion gets semantic recall *and* literal recall. Validate with eval (B4 harness) — hybrid vs dense-only on the leaderboard.
- **Prereq met:** OpenSearch BM25 index populated + incrementally maintained (✅ B65). **Feeds B70** (agentic RAG) — the retriever it would call.

### B69 — Platform completeness / gap remediation (post-B1)
**Added 2026-06-26.** Output of the multi-agent completeness audit (`docs/completeness-audit.md`) — artifacts that "run once" but aren't operationally complete (trigger / lineage / GitOps-reproducibility / monitoring / docs). **Data-mesh-scoped gaps (14) are solved inline as part of B1**; this item is the **platform-wide set (28: 9 high / 14 med / 5 low)**, to clear **immediately after B1 lands**. Full register: `docs/completeness-audit.md`. Highlights (high):
- **Secrets management** — ~25 imperative-only cluster secrets, nothing restores them → adopt SealedSecrets/External-Secrets/SOPS (or commit `*-secret.example.yaml` shapes + `runbooks/secrets.md`). **DataHub-specific: DataHub Secrets (NEO4J_PASSWORD, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, GRAFANA_SA_TOKEN) are wiped on every GMS restart** — they live in GMS memory, not Postgres. Must be re-entered after every GMS pod restart. Fix = configure DataHub to persist secrets to the Postgres backend, or pre-seed them via the GMS API on startup.
- **No dead-man's-switch** — Alertmanager Watchdog routed to `null`; a total alerting-pipeline failure is silent → external heartbeat.
- **Always-firing `telegram-test` alert** committed + Argo-synced (`expr: vector(1)`) → pages every 4h; delete from git.
- **Ollama / Hermes / tool-server** — no monitoring + not reproducible from git (image `:local`/Never → ErrImageNeverPull on rebuild).
- **Istio set not onboarded to Argo** (incl. STRICT mTLS PeerAuthentication — load-bearing).
- **Kuma monitors only in SQLite**, LGTM doesn't monitor itself, forward-auth is a SPOF with no probes.
- **Prometheus scrape coverage is sparse (surfaced 2026-06-27).** Most pre-B65 services have **no ServiceMonitor** — the monitoring gate was never applied *retroactively*, so only the newer components (data-mesh, Trino) are scraped + alerted. **Audit:** `count(up) by (job)` lists every live scrape target → anything absent has no ServiceMonitor. Remediation = add ServiceMonitor + a PrometheusRule (down/error alert → Alertmanager → Telegram) per gap, prioritizing the load-bearing services. The completeness gate keeps every *new* store covered going forward; this is the retroactive backfill.
- **GizmoSQL external TLS (added 2026-06-27)** — the DuckDB Flight SQL **in-cluster** hop is Istio mTLS, but the **external IDEA→NodePort hop is plaintext over the LAN** (password in the clear; the flagged in-cluster `TLS_SKIP_VERIFY` is already gone). Fix = a **gRPC-TLS ingress at `gizmosql.weyland.lab`** (Traefik terminates the real wildcard cert, forwards h2c into the mesh) → IDEA connects TLS with a valid cert, no skip-verify. Low risk on a trusted home LAN; the honest finish for the GizmoSQL gate.
- **Grafana datasource audit + dashboards** — as new data stores are added (TimescaleDB, future Tier-2 stores), audit Grafana datasources to ensure all active stores are registered and have dashboards. Current known gap: TimescaleDB added 2026-06-28, datasource registered manually but no dashboards built yet. Build Grafana dashboards for TimescaleDB hypertables (eval score trends, guardrail verdict rates, Dagster run durations, DataHub ingestion health).
- Plus medium/low: eval-leaderboard frozen, uncodified crons (roadmap-sync, ai_session, docs-site rebuild, code scans), loose `k8s/` root files not in Argo, several stale backlog "done"/count claims.

### B70 — Agentic RAG on LangGraph + MLflow tracing
**Added 2026-06-26.** Bring **LangChain/LangGraph** into the stack (lab experimentation + a real capability, not a reskin). Build a **LangGraph agentic-RAG control loop** — retrieve → reason → *reflect / re-retrieve if weak* → answer — over the existing vector backends (pgvector/Qdrant/Weaviate/Neo4j), more capable than the current single-shot LlamaIndex `/context/ask`. Instrument with **`mlflow.langchain.autolog()`** → MLflow **Traces** tab (per-step LLM/tool/retrieval spans = GenAI observability Tempo's mesh traces can't give: prompt/context/answer per step).
- **Feeds B66** (Operator Agent Platform) — doubles as a LangGraph spike for the agent-framework decision.
- **Location:** a new agentic path in `weyland-tool-server` (or a sibling service). Note the tool-server image is `:local`/`imagePullPolicy:Never` → mind the **B69** reproducibility gap on rebuild.
- **Completeness gate** applies on build (trigger / lineage / GitOps / monitoring / docs).

### B71 — DataHub domains + ownership (governance pass)
**Added 2026-06-26.** The catalog has datasets but **no domains, no ownership** — and domain-oriented ownership is the *organizing principle* of the data mesh (part of B1's governance layer alongside Keycloak/Ranger/OPA/Soda). Promote the existing **Dagster groups** (already emitted as `dagster_group` tags: default/RAG, eval, catalog, aidlc_kb, ai_session) into real DataHub **Domains** (likely consolidated — *RAG Platform · Eval · Model Catalog · Knowledge Base*), and assign **ownership** (a "Weyland" group / emangini as Technical Owner). Apply three ways (mix):
1. **Ingestion recipes** — `domain:` (pattern→domain) + `owners:` config so the pull sources (Postgres/Grafana/Neo4j/MLflow/Iceberg) auto-file on every run.
2. **`datahub_emit.py`** — extend to emit Domain + Ownership for the Dagster assets (the group→domain mapping is half-built since we already emit the group tag).
3. **csv-enricher ([B68])** — bulk-assign domains/owners/tags to existing entities from a CSV/Sheet. A **URN → domain → owner** mapping *is* the "sheets" B68 was blocked on — so B71 unblocks/uses B68.
- Makes everything cataloged this session (Dagster/Grafana/Iceberg/MLflow/Neo4j/Postgres) navigable. Strong candidate to do next.

### B75 — Additional music datasources (Core — data expansion)
**Added 2026-06-28. Updated 2026-06-29.** Music datasets added to the `music` lakeFS repo:
- **MSD (UCI subset)** ✅ — UCI YearPredictionMSD (515k songs, 90 audio features). Full MSD → B76.
- **Last.fm** ✅ — `matthewfranglen/lastfm-360k` (HuggingFace, 13.9M rows, user listening history).
- **MusicBrainz** ✅ — `seungheondoh/music-wiki` (HuggingFace, 11 entity configs: artist/release/genre/etc.).
- **GTZAN** ✅ — `marsyas/gtzan` (HuggingFace, 1k songs, 10 genres, genre classification benchmark).
- **LP-MusicCaps-MC** ✅ — `seungheondoh/LP-MusicCaps-MC` (HuggingFace, 5.5k rows, music captioning).
- **LP-MusicCaps-MTT** ✅ — `seungheondoh/LP-MusicCaps-MTT` (HuggingFace, 22k audio/88k captions, audio tagging).
- **AudioSet (balanced)** ✅ — `agkphysics/AudioSet` balanced (HuggingFace, 35k clips, 527 audio event labels, CC-BY-4.0).
- **Spotify Charts** — removed (Kaggle requires login, no free public source).
All land in lakeFS → Parquet → Iceberg → Trino/DuckDB queryable. Gated datasets → B76.

### B76 — Full MSD + Music4All + MTG-Jamendo (Core — data expansion)
**Added 2026-06-29.** Three gated/large music datasets to pursue when access is available:

**Million Song Dataset (full 1M songs) via AWS snapshot:**
- Currently using UCI 515k-song subset as a substitute
- Full MSD available as AWS public dataset snapshot (~300GB)
- AWS snapshot workflow: (1) Launch EC2 in `us-east-1`; (2) `aws s3 sync s3://millionsongdataset/ .`; (3) convert HDF5 → Parquet → upload to lab MinIO. Spot instance ~$5 for the copy.
- University copies: Drexel, Ithaca College, QMUL, NYU, UCSD, UPF have institutional copies
- Prereq: AWS account + ~300GB temporary storage

**Music4All (109k songs, Spotify audio features + lyrics + metadata):**
- HuggingFace: `m-a-p/Music4All` — gated, requires approved access request
- Most similar to MSD in scope; request access at huggingface.co/datasets/m-a-p/Music4All

**MTG-Jamendo (55k Creative Commons songs, 195 tags):**
- Official HuggingFace: `MTG/mtg-jamendo-dataset` — gated
- Community mirror: `rkstgr/mtg-jamendo` — public but 118GB audio
- From the Music Technology Group at UPF (same institution with MSD copy)
- Practical path: metadata-only CSV from `mtg-jamendo.com/data/` (no audio download needed)

### U18 — weyland-lab SSH key full lockdown (rogueone-side)
- **✅ DONE 2026-06-17 — closed as KEY RETIREMENT.** Removed the rogueone `authorized_keys` line and deleted
  the orphaned `weyland-lab-ssh-key` k8s Secret. The key is fully gone (no public half, no private half).
- **⛔ Original lockdown scope OBSOLETE (the work below is void) — reframed to retirement (2026-06-17).** B25b replaced the Dagster
  SFTP-from-rogueone ingestion with a GitHub git-pull — `source_document.py` no longer SSHes rogueone.
  Repo grep (`weyland-lab|WEYLAND_SSH|paramiko|authorized_keys` over `nodes/` + `k8s/`) finds **zero**
  consumers — only the repo-name in GitHub URLs. The `weyland-lab` key is **dead access**. The original
  "lock the key down" scope is void; the residual task is **retire the key** (a deleted key beats a hardened
  one): (1) remove the `weyland-lab` line from rogueone `~/.ssh/authorized_keys`; (2) drop any orphaned k8s
  Secret that held the private key (no manifest references it); (3) delete the private key file if any.
  ~5 min, host-side, no image rebuild. **DROP the lockdown scope below — kept for context only.**
- **Origin**: U11 follow-up (deferred option (c), agreed 2026-06-09)
- **Theme**: E — hardening
- **Scope**: Tighten the (now single-purpose) weyland-lab key on rogueone's
  `authorized_keys`: `restrict`, `from="<mother>"`, and a forced `command="cat <file>"`.
  The forced command requires switching Dagster `source_document.py` from SFTP to
  `exec_command("cat <file>")`. End state: even if the key leaks it can only read the one
  source file, from mother, no shell. (Host-key pinning is done separately in U11 (b).)
- **Requires**: Dagster user-code image rebuild + an ingestion test run; rogueone
  authorized_keys edit. Touches the active ingestion path — validate carefully.

---

## Iteration 1 follow-ups (banked, see units-iter1.md)
- **U17** — Migrate platform API routes APISIX→Traefik; APISIX→outliers-only. **DROPPED as stale.**
- **U18** — weyland-lab SSH key. ✅ **DONE 2026-06-17 as KEY RETIREMENT** (B25b mooted the lockdown — key had
  no consumers; deleted rogueone `authorized_keys` line + orphaned k8s Secret). See detail above.

## Viz / BI (open)
- **VIZ-1 (2026-07-03)** — Build Superset charts + dashboards across ALL connected databases (Trino, the 11
  Postgres, TimescaleDB, and now **ClickHouse** with its bulk-registered `datasets_*` tables — plus future
  stores). Today only the "Weyland Platform Overview" dashboard exists; the Tier-2 dataset stores are
  connected/registered but un-visualized. A dedicated BI pass: a dashboard per domain (music/health) +
  cross-store exploration. Datasets are registered (see `scripts/superset_bulk_clickhouse.py`) — this is the
  chart/dashboard authoring on top.

## Tech-debt / Security (open)
- **SEC-1 (2026-07-03)** — Migrate Tier-2 store creds off inline `weyland_dev_password` in
  `k8s/dagster/user-code.yaml` (`TIMESCALEDB_/MYSQL_/MONGO_/CLICKHOUSE_PASSWORD`) → a k8s Secret + `secretKeyRef`,
  and **rotate** the value. Flagged twice by the automated security review. Low-risk on the LAN, but the password
  is committed in git. Do **all four at once** — piecemeal (ClickHouse-only) is inconsistent and gives no real
  benefit while the other three stay inline. Also the ClickHouse `users.d` Secret is already out-of-band (good).

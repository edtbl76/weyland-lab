# Weyland Forward Roadmap — re-prioritized 2026-06-14

Re-ordered per RE-grounded audit (aidlc-docs/inception/backlog-reprioritization.md). Immediate directives: B29 (connect Claude Code to weyland MCP) and B25 (docs IA + git RAG ingestion). Three priority groups: Real Purpose / Extras+Optimization / Hardware-Gated.

> **Agent topology — RESOLVED 2026-07-23 (supersedes the 2026-06-14 Hermes-vs-OpenClaw framing).** Both legacy agents
> are **retired**: Hermes (CT-104) destroyed 2026-07-23, OpenClaw canceled (B28). The agent lane is now ONE thing — the
> **B66 operator agent**: a fresh LangGraph pod on **mother** with a local **`gpt-oss:20b`** brain (bake-off: ties Claude
> Haiku on operator tool-use, incl. the act-path safety test — `demos/brain-bakeoff.md`), Telegram long-poll ingress,
> and the tool-server `/mcp-act` plane (job-allowlist + confirm-step). No more "which agent" / "both agents" — read older
> references to Hermes/OpenClaw below as **the operator**. See B66 + [[b66-operator-brain-bakeoff]], [[openclaw-deprioritized]].

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
- **B2** — Hermes agent platform (OpenClaw sibling) — ✂️ **CLOSED 2026-08-05 — superseded by B66** (`weyland-operator`; Hermes CT-104 destroyed 2026-07-23, the operator lane rebuilt in B66 + the local-brain work). Historical: **v1 LIVE 2026-06-14**: Hermes CT 104 on `qwen3-coder:30b` (MoE); read-only **system-view MCP server** (4 tools: status/context_search/context_ask/list_models) built into the tool-server via `fastapi-mcp` `mount_http()`, registered in Hermes, **validated end-to-end** (agent → MCP → live backend health). **Telegram gateway front door LIVE 2026-06-14** (allowlisted DM → agent reply). Runbook docs/runbooks/agent-hermes.md · design docs/concepts/agent-platform-design.md.
- **B23** — Break out `arch.md` component diagrams — ✅ **DONE (2026-06-14)**: created `docs/diagrams/` with full C4 hierarchy (L1 context, L2 container, L3 component × 6: mother/hermes/ollama/whisper/openclaw/rogueone) + 5 Mermaid sequence flow diagrams = 13 files total. arch.md rewritten as narrative + embedded C4Context + links to all diagrams. Note: Mermaid C4 renderer is basic — consider Structurizr at B25 IA overhaul time.
- **B29** — Connect Claude Code → weyland system-view MCP — ✅ **DONE (2026-06-14)**: registered via `claude mcp add weyland --transport http http://192.168.1.243:30080/mcp`; validated live — `status` tool returned all 4 backends ok + 6 Ollama models. Claude Code is now a first-class MCP consumer alongside Hermes.

---

## Priority — work top-down

### Immediate
1. **B31** — Codebase audit / restructure (`nodes/`) — **AUDIT DONE 2026-06-15.** Tree is clean: retired 2 dead bootstrap scripts; flagged 1 committed secret (gitignored — needs untrack+rotate, your task); OpenClaw scripts → B28, watcher → B25b. No restructure needed. See detail below.
2. **B25** — Docs + codebase RAG ingestion — ✅ **DONE 2026-06-15.** B25a (docs restructure) + B25b (Dagster git-pull of `docs/` + `nodes/`, dual chunking) live & validated end-to-end: 40 markdown + 76 code docs in the RAG (was 1), code retrievable via the MCP from Claude Code. Watcher retired. **Orphan reconciliation** (prune sources no longer in the repo across all 4 backends) + **eval-corpus markdown filter** added & validated 2026-06-15 (the old `obsidian` orphan auto-pruned on the next run). See detail below.

### Platform Foundation
4. **B24** — Evaluate nerdctl — ✅ **EVALUATED 2026-06-15 → DECLINE.** Keep docker + `save|import` as a deliberate build↔runtime anti-corruption layer; nerdctl's only real win (build into k3s's live image store) violates it, and keeping docker alongside would only add daemons. See detail below.
5. **B14** — Guardrails + Hermes read+act — ✅ **DONE 2026-06-15.** Both halves shipped: guardrail I/O layer (injection/toxicity/grounding on `/context/*`) + read+act (act-tools on `/mcp-act`, `act` hook audits to `guardrail_verdicts` with the `actor` seam), all `mode=shadow` (record-only — the right default for a single-user LAN lab). Shadow plumbing is complete; the enforcement *promotions* are carved out as their own downstream items, not B14 scope: grounding `shadow→flag/block` calibration → **B35** (✅ done), act policy gate → **B17+B19** (needs the gateway `actor`), PII bake → **B34**, gateway auth/actor injection → **B17+B19**. See detail below.
6. **B26** — Hosted-model gateway (LiteLLM) + model catalog — ✅ **DONE 2026-06-17** (reframed from "Hermes Claude brain"; Claude path declined — ToS gray area). LiteLLM on mother fronts all Gemini+OpenRouter; Dagster `model_catalog` (6h). See detail below.
7. **B27** — Hermes Kanban (self-management + roadmap co-pilot) — ✅ **DONE 2026-06-17.** Native SQLite kanban; planning on Gemini-free via the gateway (`kanban_decomposer`/`triage_specifier` pinned), workers local; `weyland-roadmap` board mirrors this backlog one-way (`roadmap-sync.py`, 6h cron). See detail below + [runbooks/agent-hermes.md](runbooks/agent-hermes.md#kanban--self-management--roadmap-co-pilot-b27-live-2026-06-17).
8. **B8** — Istio service mesh — ✅ **DONE (status flipped 2026-08-05)** — the mesh is live + pervasive: **STRICT-mTLS Postgres**, sidecar injection across services, **DestinationRules** (Neo4j-Bolt keepalive), **AuthorizationPolicies** (tool-server act endpoints → gateway SPIFFE identity); Traefik stays the ingress. Ran past the original slice plan. Historical: **DECIDED BUILD-NOW 2026-06-17** (all four drivers: mTLS/observability/traffic-mgmt/learning). Design: `aidlc-docs/construction/b8-istio-design.md` — Approach 1 (sidecar, contained tool-server slice, bookinfo warm-up); step-0 mother-headroom gate → pivot to ambient if tight; **slice 1 = PERMISSIVE everywhere** (tool-server serves external NodePort MCP; backends serve un-meshed Dagster) — STRICT enforcement deferred to slice 2 (mesh Dagster); Traefik stays the ingress. See detail below.
- **B37** — **Ingest the AIDLC knowledge repositories into the (Graph) RAG** — ✅ **DONE 2026-06-19.** ~510 brand-neutral entries ingested from MinIO into all 4 backends (`aidlc-kb/` namespace, KB-scoped hash-gate + prune); RAG answers cite KB files (DDD ← `domain-driven-design.md`/`context-mapping.md`). **Phase 2 graph live:** 510 `:Entry` nodes, 2311 `RELATED_TO` + `SURFACES_AT`/`TAGGED`/`IN_VERTICAL` edges from frontmatter (no LLM). On-demand `weyland_aidlc_kb_job`; runbook [runbooks/aidlc-kb-ingest.md](runbooks/aidlc-kb-ingest.md). Fuzzy LLM extraction → **B38**. See detail below.
9. **B3** — IDP / Backstage — **✅ RETIRED 2026-06-22 (B59)** (was a learning project — slices A+B). Fully torn down once Port reached catalog parity: app (`k8s/weyland-idp/`) + 12 `backstage_plugin_*` DBs + `weyland_idp` Postgres role + MinIO `techdocs` bucket + the `weyland_techdocs_job` Dagster asset, all removed. Replaced by **Port.io** catalog (codified in `tofu/port/`) + **`docs.weyland.lab`** (standalone MkDocs Material). B40 (Mermaid) + B42 (scaffolder) now moot. See B59.

### Data & Automation
10. **B10+B16** — MLflow (experiment tracking + model registry) — ✅ **DONE 2026-06-19.** Live at `mlflow.weyland.lab` (Keycloak SSO): Postgres backend store + MinIO `mlflow` artifact bucket (proxied `--serve-artifacts`; **big models go two-plane → artifacts direct to MinIO**, see B-RT), meshed, smoke-tested end-to-end. **LAN NodePort `:30500`** for external Ray workers (B-RT). `k8s/mlflow/`. See detail below.
- **B-RT** — **Remote model training (rogueone) + persistent Ray** — **✅ DONE 2026-07-06.** MinIO-backed OCI **registry** (`registry.weyland.lab`) → self-contained **trainer container** on rogueone (kubeconfig-only: self-fetches creds + own port-forwards) → **MLflow with artifacts DIRECT to MinIO** (bypasses the serve-artifacts proxy that timed a big model out through the 1Gi pod). **Persistent Ray cluster:** always-on **head** on mother (`ray.weyland.lab`, `k8s/ray/`, **plain Ray not KubeRay**, hostNetwork, `--num-cpus=0` coordinator) + **rogueone as a permanent native systemd edge worker** (`ray-worker.service`; not-always-up → drops on sleep, auto-rejoins on wake). Submit via `ray job submit`; **`--tune`** = a Ray Tune HP sweep **across the cluster**; the **winner retrains + registers on the worker** (`@ray.remote` task — keeps the big fit off the 4Gi head). `genre_classifier` ~**v6** (Ray-Tune-best f1 **~0.308**). **Hardened:** MLflow **LAN NodePort `:30500`** iptables-pinned to rogueone (`externalTrafficPolicy: Local` for source-IP); MinIO TLS **verified via `AWS_CA_BUNDLE`** (mkcert root — replaced `MLFLOW_S3_IGNORE_TLS`); Ray dashboard Keycloak-gated. **Parity lesson:** the native worker must exactly match the head's Python patch (3.11.9) + Ray + serialization libs (pyarrow/numpy/**boto3/botocore/s3transfer**) — install from the head's `pip freeze`. Runbooks: [runbooks/remote-training.md](runbooks/remote-training.md), [runbooks/mlflow-training.md](runbooks/mlflow-training.md). `services/genre-trainer/`, `services/ray-head/`, `k8s/ray/`, `k8s/registry/`. **OPEN follow-ups:**
    1. **Ray edge network-hardening (residual).** The Phase-2 edge worker is live, but network *segmentation* isn't: `hostNetwork` exposes the unauth Ray dashboard/Jobs API on the LAN + the MLflow NodePort is iptables-pinned (not VLAN-isolated), and the iptables pin is **not yet reboot-persistent**. Proper fix = a segmented VLAN/firewall allow-list (head Ray ports + MLflow/MinIO/lakeFS only) + Ray TLS / join-token + persist the nft/iptables rule. Rationale: Ray is *not* a security boundary → constrain at the network (DMZ).
    2. **Feast source (`--source feast`) — ✅ DONE 2026-07-06.** The wrinkle (offline store = STRICT-mTLS Postgres, unreachable from the external trainer / hostNetwork head) is solved by splitting the layers: a **meshed Dagster asset `genre_feast_training_set`** runs `get_historical_features` (point-in-time) → writes `music/parquet/genre_feast_training/` to lakeFS; the trainer's `--source feast` reads that parquet + fits it exactly like silver → `genre_classifier` **v7** (f1 0.314 ≈ silver, the UC2/UC3 parity point). Retired the superseded in-cluster `mlflow_genre_from_{silver,feast}` assets (+ trimmed dead sklearn/full-mlflow deps). On-demand: materialize the asset before a feast run. Runbook: mlflow-training.md UC2; diagram: flow-feast.md; asset: `weyland_pipeline/assets/genre_feast_training.py`.
    3. **Registry web UI — ✅ DONE 2026-07-07.** `joxit/docker-registry-ui` at `registry-ui.weyland.lab` (nginx-**proxy mode** → the in-cluster registry svc, so no CORS on the registry; Keycloak forward-auth). `k8s/registry/registry-ui.yaml` (rides the `registry` Argo app). Working — browses the catalog + tags.
    4. **Ray observability → Prometheus + Grafana — ✅ DONE 2026-07-07.** Head exports `ray start --metrics-export-port=8080` + `k8s/ray/servicemonitor.yaml` scrapes it; the **rogueone worker also exports `:8080`** (`ray-worker.service`) and Prometheus scrapes it via a **static target** (`additionalScrapeConfigs` → `192.168.1.230:8080`, in the kube-prometheus values) — the **task/actor/node `ray_*` metrics live on the WORKER** (the head is a `--num-cpus=0` coordinator with none; head-only scrape → empty panels). Ray's shipped Grafana dashboards imported via `k8s/monitoring/ray-grafana-dashboards.yaml` (ConfigMap, `grafana_dashboard` sidecar label) — needed **`ServerSideApply`** (465 KB > the 256 KB last-applied-annotation limit). The Ray dashboard **Metrics-tab embed** works via `RAY_PROMETHEUS_HOST`/`RAY_GRAFANA_HOST`/`RAY_GRAFANA_IFRAME_HOST` on the head + Grafana `allow_embedding: true` — **no Keycloak wrinkle after all** (`ray`+`grafana.weyland.lab` are the same site → the SSO cookie carries into the iframe). Read them at **`grafana.weyland.lab → Dashboards → Ray`** (the in-tab embed is a heavy iframe swarm — native is the sane view). Worker-scrape rides the edge posture (firewall `.230:8080` when the DMZ lands).
    5. **Feast UI — ✅ DONE 2026-07-07.** `feast ui` at `feast-ui.weyland.lab` (Keycloak forward-auth, meshed for the STRICT-mTLS SQL registry; `k8s/data-mesh/feast-ui.yaml`). **The fight:** feast 0.58's pip package ships a UI bundle that **predates its own REST backend** — the frontend does a single `GET registryPath` expecting a **`registry.json` dump** (its own embedded example), but feast hardcodes `registryPath=/api/v1` (the REST base, served piecemeal) → empty UI. Also needed `grpcio grpcio-health-checking grpcio-reflection` in `Dockerfile.feast` (feast ui's REST mode imports the gRPC registry server; `feast serve` doesn't). **Fix (deterministic, no version gamble):** a ConfigMap launcher runs `feast ui`, then overwrites its `projects-list.json` to `registryPath=/registry.json` and generates that dump (`MessageToJson(registry.proto())`) into the served UI dir, refreshed on an interval — renders the 2 views / entities / services. **Bonus:** the `genre_feast_training_set` asset now registers a feast **SavedDataset**, populating the Datasets tab + adding lineage. Cross-ref **B1.8**. (Items 3/4/5 all ✅ — the "give the capability a face" + observability batch is complete.)
11. **B1** — **Data mesh — the Iteration-2 platform build.** ✅ **DONE (core, 2026-08-05)** — the mesh is built + live: all slices shipped (B1.1 Keycloak SSO · B1.2 Nessie/lakeFS · B1.5 dbt · B1.6 governance DataHub/Ranger/Soda · B1.7 Cube · B1.8 Jupyter) + the stores (ClickHouse/Cassandra/Qdrant/Weaviate/Neo4j/Feast), Trino, OpenLineage, and the operator queries it via the fleet MCPs. **Maturity tails split into their own items** (B77 DQ, B78 vector polish, B80 DataHub, B81 Jupyter, B113 financial domain) — **TODO: collapse those into one "data-mesh maturity" bucket** when we reach them in the triage. Historical design: FULL design locked in `aidlc-docs/data-mesh-design.md` (~30 techs across 8 layers; single-node **run-mode tiered** — always-on foundation vs KEDA/operator on-demand). The **3 data products are the *output*** — they ride on the platform below, they are NOT the build. Sequenced into dependency-ordered slices (storage→catalog/gov→query→transform→consumption); **Keycloak pulled to the front** (lab-wide SSO, not mesh-specific — pays off immediately):
    - **B1.1 — Identity / SSO (Keycloak)** — **✅ DONE 2026-06-24.** Keycloak (`keycloak.weyland.lab`, `weyland` realm, k8s + meshed Postgres) = lab IdP; realm + clients in `tofu/keycloak/`. **6 apps cut over:** OIDC native (Grafana — hardened/CA-verified · GlitchTip — via a DB-precreated allauth social link · Open WebUI) + **forward-auth** via `traefik-forward-auth` (`auth.weyland.lab`, MLflow/Kiali/filestash; cookie domain `weyland.lab` = one login + single logout `/_oauth/logout`). **Woodpecker left on GitHub-forge auth** (no generic OIDC); MinIO console dead → storage SSO = forward-auth on **filestash**, S3 API stays on access keys. **Gating EXTENDED 2026-06-25 → every browser UI** (forward-auth added to Unleash/SonarQube/Uptime-Kuma/Dagster/n8n/Woodpecker/Argo CD/Headlamp/OpenCost/LiteLLM/docs-site/APISIX-dash + Nessie/lakeFS; own-login apps = double-login). Data/API plane (S3 API, NodePort data backends, APISIX gateway) stays API-auth'd — can't browser-SSO. Gotchas (all in [[keycloak-sso-b1.1]]): Python apps need a system+mkcert CA bundle for the OIDC back-channel; cross-ns Traefik middleware blocked (local copy per ns); in-cluster DNS via `coredns-custom`; new `*.weyland.lab` subdomains need `/etc/hosts`. **Google brokering SHELVED 2026-06-24 — blocked by LAN-only:** Google OAuth rejects a `.lab` redirect URI (needs a public TLD), and the only fix is a public-domain overlay of the whole IdP (re-host Keycloak + repoint all 6 clients, since issuer = hostname) — not worth it for a solo lab; password login suffices. See [[keycloak-sso-b1.1]], [[lan-no-github-webhooks]]. (Keycloak chosen over Okta — LAN can't depend on cloud auth.)
    - **B1.2 — L1 Storage foundation** — **✅ DONE 2026-06-25.** **Nessie** (`nessie.weyland.lab` — Iceberg catalog + table versioning; Postgres `nessie` DB, warehouse = MinIO `warehouse` bucket, Iceberg REST at `/iceberg`) + **lakeFS** (`lakefs.weyland.lab` — file/dataset versioning; Postgres `lakefs` DB, blockstore = MinIO `lakefs` bucket) in a new **`data-mesh`** namespace, both meshed to STRICT Postgres. `k8s/data-mesh/`, Argo app `data-mesh`. Iceberg = the table format they enable (no service; lands with Trino/Dagster writes at B1.4+). Traps (all in [[data-mesh-b1.2-storage]]): Nessie STATIC S3 creds = a flat URN ref + a HYPHEN-FREE secret name (env vars can't express a hyphen); forward-auth gate is browser-only → CLI/API clients (lakectl, later Dagster/Trino) hit the in-cluster service directly, not the gated ingress.
    - **B1.3 — L4 Catalog** — **DataHub** (always-on centerpiece: ES + internal Kafka + GMS + frontend) + **ODCS** data contracts. Dropped Amundsen/OpenDataMeshPlatform. **ES = first-class shared service** (decided 2026-06-24): stand up DataHub's required Elasticsearch as its *own* exposed catalog service, not DataHub-internal — one ES the lab can reuse for search/log experiments (no second ES on the single node).
    - **B1.4 — L2 Query / Federation** — **Trino** (federated SQL over Iceberg/Postgres) + **DuckDB** (embedded) + **TimescaleDB** (Postgres extension, hot time-series; no InfluxDB).
    - **B1.5 — L3 Transform** — **dbt Core** + **SQLMesh** + **dlt** (EL) + **Debezium** (CDC). **✅ dbt Core BUILT 2026-07-08** — the analytics-engineering layer on the Iceberg gold: `dbt-trino` materializes **7 tested marts** (music: `mart_spotify_audio`/`mart_genre_audio_profile`/`mart_fma_genre_tree`/`mart_artist_popularity`; health: `mart_state_health_trends`/`mart_country_health`/`mart_personality_by_country`) as Iceberg tables in `iceberg.dbt` (Trino WRITES to Nessie `main`), orchestrated by **`dagster-dbt`** (`weyland_dbt_assets`, manifest baked at image build), tested with dbt-utils/dbt-expectations. Project: `services/weyland-dagster/dbt/`. Gotchas (see [[dbt-transform-tier]]): **Trino's 2G heap + `-XX:+ExitOnOutOfMemoryError` OOM-crashlooped** under dbt's Iceberg aggregations (looked like "Trino down" — only RESTARTS climbed) → bumped heap 2→4G / limit 3→6Gi + `approx_distinct` + threads:2; staging ephemeral; `mart_food_nutrition` blocked (its `food_nutrient` 26.8M was deferred from Iceberg by the >15M writer cap) + `mart_genre_crosswalk` deferred (a curated genre seed, not a clean join). **Remaining B1.5:** DataHub dbt connector (models/tests/lineage), schedule the dbt asset, the payoff (repoint trainer/Feast at the marts), **SQLMesh** (evaluate-later). **✅ Streaming tier BUILT 2026-07-04/05** (Redpanda broker+Schema-Registry+Console · Avro event-replay producer `datasets.*` · DataHub kafka source · Debezium CDC `cdc.*` on musicbrainz-postgres — all 4 ops, full before-image, Avro-serialized; runbook [runbooks/streaming.md](runbooks/streaming.md), diagrams flow-streaming/flow-cdc). **Platform decided 2026-07-04:** **Redpanda = the always-on data plane** (Kafka-wire broker + built-in Schema Registry in one binary; serves the grid `Redpanda`/`Avro/Kafka` column, the Avro event-stream demo (B73), Debezium CDC via a Kafka Connect worker, and the future Flink target — all one broker). Isolated from DataHub's internal Kafka (its metadata bus — do NOT stream data through it; DataHub resets would nuke our topics; mirrors the "ES as own service, not DataHub-internal" B1.3 precedent). **Strimzi — EVALUATED + DECLINED 2026-07-05:** none of its three workflows earn their place in a $0 single-node lab that already has working Kafka (ISR = an Apache-Kafka replication detail Redpanda doesn't use, only at multi-broker RF≥2; KEDA lag-scaler = no real variable-load consumer to scale; declarative-CDC = overkill for one connector, solvable by committing the connector JSON without the operator). Value was the streaming tier itself. Revisit only on a genuine multi-broker/HA need. **Flink** streaming stays on-demand (KEDA + Flink Operator → Redpanda). Catalog Kafka in DataHub via the native `kafka` source pointed at **Redpanda** (closes the one open B65 catalog target). No Airflow/Airbyte. Grid: `docs/data-domain-storage-grid.csv` now has a leftmost **Redpanda** column, Y only for the stream-shaped sets (lastfm listen events, big_five/brfss/nhis survey streams).
    - **B1.6 — L5 Governance** — **OpenLineage** (Dagster→DataHub, drop Marquez) + **Ranger** (data-plane authz: Trino column/row masking) + **OPA** (control-plane Rego) + **Soda** DQ (dbt-expectations already in-pipeline from B1.5). **✅ Ranger DONE 2026-07-10** (Slice A — `ranger.weyland.lab`, Trino native ranger plugin enforcing, column masking proven; runbook `ranger.md`, [[ranger-trino-authz-b-l5]]). **✅ OPA/Gatekeeper DONE 2026-07-10** (Slice B — admission control, 3 dryrun constraints (no-latest/mem-limits/owner) + cluster remediation: all always-on pods now have mem-limits, `:latest`→digests, owner labels; GPM Report UI `gatekeeper.weyland.lab` + 6-panel Grafana dashboard). **✅ Soda DONE 2026-07-10** (Slice C — 53 checks over 7 marts via `soda_quality_job`, isolated `/opt/soda-venv` + `trino-noauth` proxy, results → **DataHub Assertions** (`emit_soda_assertions`); caught+fixed 7 all-NULL columns in `mart_country_health` (WHO `dim1` code-vs-label); runbook `soda.md`, [[soda-dq-l5-slice-c]]). **B1.6 L5 (A+B+C) COMPLETE** — OpenLineage (Dagster→DataHub) is the one remaining L5 stretch item, deferred. (Also this session: **DataHub governance layer** — domains/products/2 glossaries/structured-properties/docs-links, all emitted from git ([[datahub-governance-layer]]) — folds in B65/B71/B1.3-contracts; **dbt DataHub connector** + Lightdash from B1.5.)
    - **B1.7 — L6+L7 Consumption** — **Cube** (semantic layer) + **dbt Semantic Layer/MetricFlow** + **Lightdash** + **Superset** (BI, both on-demand). No Metabase. **✅ Cube + MetricFlow DONE 2026-07-12** (first builds after B79 freed the node). **Cube** (`cubejs/cube`, `k8s/cube/cube.yaml`, `cube.weyland.lab`): headless semantic API over the 7 marts via trino-noauth, SQL(:15432)/REST/GraphQL, Keycloak-gated; proven end-to-end (top-danceable-genres query); its unique value vs Lightdash/dbt = a *governed metrics API for apps/agents* (see runbooks/cube.md, [[cube-semantic-layer-b1.7]]). Gotchas: model mount needs `subPath` (else ..data dup), SQL API needs `MEASURE()`, Playground is dev-only/heavy client-side → run headless. **MetricFlow** (`dbt-metricflow`, `dbt/models/semantic_models.yml` + `metricflow_time_spine.sql`): `mf query` compiles governed metrics to Trino, proven (avg life-expectancy by year, COVID dip visible). Works with dbt-trino; needs a DAY time-spine (Trino `sequence()` caps at 10k → cross-join two sequences for the 1960–2026 calendar); int-`year` marts → cast to DATE; scoped to the time-shaped health marts (music marts are categorical-only, not a MetricFlow fit). Lightdash + Superset already done (B1.5/B65). Remaining B1.7 polish: pin Cube image + Argo app; wire Superset→Cube SQL API.
    - **B1.8 — L8 Data Science** — **JupyterHub** (KubeSpawner) + **Feast** (feature store, reuses Postgres) + **Ray**, on-demand. **Feast ✅ DONE 2026-07-05** (built ahead as a capability): registry+offline=Postgres `feast` DB, online=Valkey; 2 views (spotify audio features / brfss chronic-condition prevalence — honest cut from the grid's 14); online serving by entity key (SDK + **feast-server** REST at feast.weyland.lab, `/docs` Swagger) + point-in-time training retrieval (CA-2013≠CA-2019, leakage-free) + registry/train-serve consistency. Slim feast image, MESHED in data-mesh (STRICT-mTLS Postgres). Runbook: datasets-hydration.md; diagram: flow-feast.md; queries: query/feast.md. **Ray ✅ DONE 2026-07-06** (persistent head on mother `ray.weyland.lab` + rogueone permanent native edge worker + Ray Tune sweeps → MLflow; **plain Ray, not KubeRay** — edge/external nodes need a plain `ray start` cluster; see **B-RT**). JupyterHub still deferred. **Scope add 2026-06-27:** first deliverable = a **polars notebook that queries all 4 datasets-lake silver formats** (Parquet · Arrow · Avro · Lance) from lakeFS **in-cluster** — JupyterHub is polars' proper home (native lakeFS/MinIO access → no port-forward, venv, or TLS-cert friction). Seed = `nodes/mother/lab/weyland-platform/scripts/query_datasets_formats.py` (the rogueone harness). DuckDB+pyarrow exploration lands here too once that store exists.
    - **B1.9 — The 3 data products → REFRAMED 2026-07-16 (platform-complete; B1 DONE).** The mesh already publishes **9 data products** (`_PRODUCTS` in `datahub_emit.py`: Spotify Audio · Artist Popularity · Genre Taxonomy · Chronic Health Trends · Global Health Indicators · Personality Profiles · Weyland Docs · AIDLC KB · Genre Classifier) + **AI-Dev Usage** (B62, Port) — the *output* the platform was built to enable already exists. The original trio doesn't survive scrutiny: (2) store-inventory → lineage/observability is **already shipped** (OpenLineage + DataHub lineage + Port + Grafana/Kuma); (3) model-tuning feed is **parts that already exist** (Feast ✅ + MLflow ✅ + Ray ✅ — wiring, not a build). Only (1) **model-eval** warrants a real build, and even that *productizes* the existing **B4** judge-panel leaderboard rather than starting fresh → spun out to **B84**. Building "3 products" to hit the number 3 = box-checking; declined. **B1.9 closed as platform-complete; B1 = DONE.**

### Maturity / Hardening / Polish
12. **B15** — Local-model coding agents (opencode / Cline / Pi / Codex) — **✅ DONE 2026-07-27** (3 harnesses proven in-hand; best driver = ChatGPT-sub GPT-5.5 via Cline/Codex, best keyed-free = Mistral/OpenRouter; local-on-16GB not viable; gateway not usable for agentic — direct-to-provider; Groq punted on broken signup). See detail below.
13. **B17+B19** — "Mesh": A2A evaluation + MCP gateway — MERGED; same inflection point (fleet is real, govern it). **MCP-gateway half ✅ CLOSED 2026-08-01** — Ph1-2 auth/actor gate + Ph3 read-only fleet + Ph3b Bifrost agent-edge + Claude Code/Codex skill marketplace (built out as B111). **A2A-eval half — core BUILT & LIVE 2026-08-01** — the **Realm of Agents**: 24 corpus-backed specialists in 5 Norse-named groups in one multiplexed pod; Gná dispatch + two-mode leads delegating to members (LangGraph in-realm) + cross-service hand-off from the operator (`delegate_to_realm`); on Claude Haiku, tools via the Bifrost VK, MLflow-traced. Roster complete. **A2A-eval half ✅ CLOSED 2026-08-02 — DoD landed: (1) UI — the **A2A Inspector** (`inspector.weyland.lab`, Argo-managed) for debug + a bespoke **Realm Console** (`realm.weyland.lab/`: live god-map + inline execution-trace tree + streamed answer, driven by the `/route/stream` SSE); (2) per-Realm spend attribution via the **`realm-llm` Bifrost VK** (LiteLLM→Bifrost egress) — a LiteLLM-native VK is intentionally skipped (needs a LiteLLM DB, redundant given Bifrost); (3) `role-<key>` prompts registered in the Bifrost prompt-repo.** See detail below.
14. **U18** — ✅ **DONE 2026-06-17 (as KEY RETIREMENT, not lockdown).** B25b removed the SFTP ingestion that U18 was hardening → the `weyland-lab` key had zero consumers (repo grep clean). Retired it instead: deleted rogueone `authorized_keys` line + the orphaned `weyland-lab-ssh-key` k8s Secret. See detail below.
15. **B20** — Home Assistant integration — ⚪ **LOW (2026-08-05).** a **generic** HA act-tool (lights/sensors/switches → Google Home/Alexa/physical devices) for the **B66 operator** / MCP gateway (Hermes retired). Prerequisites: a running HA instance + long-lived token; physical side effects → goes through the guard/act layer. See detail below.
16. **B28** — OpenClaw rehabilitation (or retire) — **✅ RESOLVED 2026-06-25: SUPERSEDED by B66.** The keep/retire/reuse decision is no longer standalone — it's the "base agent" workstream of the consolidated [B66] Operator Agent Platform (Hermes-base vs reuse-OpenClaw's-responsiveness, decided at B66 build time). OpenClaw is NOT auto-retired (reuse candidate). Both original Qs (keep-vs-retire, refactor-vs-rewrite) move to B66.
17. **U14** — n8n workflow → git — ⚪ **LOW (2026-08-05).** audit active n8n workflows before working on this. See detail below.
18. **B34** — Evaluate + bake PII guard — ✅ **DONE 2026-07-29.** Baked presidio + ai4privacy NER, activated `llm_guard.pii` (SHADOW). Recall proven; entity set calibrated on real answers (dropped IP/UUID/CRYPTO noise, kept regex-precise + PERSON). Measured FP: 3/20, **all false positives** (NER tags tech nouns as PERSON) — so it **stays shadow/advisory**, enforcement value is on the export/PII-data paths not RAG-over-docs. Also shipped a live guard mode toggle (`/admin/mode`, Bearer-gated). See detail below.
19. **B35** — Grounding guard calibration — ✅ **DONE 2026-07-28.** Switched whole-answer→**sentence-level** scoring (whole-answer NLI over-flagged 58%), calibrated the threshold `0.5`→**`0.15`** from labeled golden-set shadow data, and found grounding.nli measures chunk-**attributability** not faithfulness → **kept in shadow/advisory** (true faithfulness gating = LLM-judge lane B84). Fixed an OOM the heavier scorer introduced (2Gi→2560Mi + bounded/serialized NLI). See detail below.
- **B36** — Hermes dashboard performance — ⚰️ **MOOT 2026-07-23** (Hermes retired; the dashboard died with CT-104). The B66 operator has no such web dashboard.
- **B46** — **Build out the Stud.io product backlog** — ✅ **DONE 2026-08-12** (summary at end of entry). Stud.io has no backlog/roadmap yet. Assemble it (audit the repo, define epics + items), then dump into the Linear **Stud.IO** project (same treatment as the Weyland dump). **The LAST of the Core work — High + Core, sequenced last (NOT maturity/polish; it's a real product target).** **Seed item (from the B60 Port audit, 2026-06-23):** stud.io has real **test + production** envs (containerized, Woodpecker-deployed) — wire its deploy pipeline to emit `deployment` events → Port `environment` entities (Test/Production) so the **deployment-frequency DORA** lights up for stud.io (the one DORA pillar PR/CI metrics don't cover: "how often do I ship to prod"). Cheap once the pipeline's already moving — lands naturally alongside the **B57** farm migration. **✅ DONE 2026-08-12:** assembled the Stud.IO backlog and dumped it into the Linear **Stud.IO** project — **8 epics (EMA-148…155) + 29 sub-issues (EMA-156…184)**. Built by **merging the user's authoritative Obsidian Kanban** (`ObsidianVault/Music & Studio/Stud.io ControlRoom KanBan`) — the curated skeleton (5 numbered modules + Long-Term backlog + Won't-DO) — with a **4-agent audit of the STUD.io repo** (`~/Documents/Studio/STUD.io`) for current status + per-module item detail + the **UX-redesign initiative the board predates**. Epics: Modules 1–5 (Plugin Scanning [In Progress] · Workflow/Task Mgmt [On Deck, ⏫] · Recommendation Engine · Audio File Scanning · Audio AI), **UX Redesign/Consolidation** (current focus; cross-linked to Module 1 — the scanner↔UX merge), **Platform & Delivery** (the DORA seed = **EMA-172**, gated on B39/B57), **Asset Manager** core enhancements. **Board forced two corrections:** "GearList Phases 2–5" were already DONE (my repo-only inference was wrong; `module-roadmap.md` is stale) → dropped; the completed Scanner Rewrite 1.17.0 isn't reflected on the (stale ~Apr) board. **Open product decision captured on the UX epic:** current look vs Matrix re-skin. Memory `stud-io-product`.
- **B73** — **Find/build uses for the datasets-lake formats** — **✅ DONE 2026-07-16** (via audit — the "inert" framing predated everything downstream). All 5 formats now have a real, strength-exercising consumer, built across the later batches: **Parquet/Iceberg → Trino/DuckDB/dbt analytics** (B65/B1.5), **Avro → Redpanda → Flink** ("Avro in motion", B1.5/B83), **Lance → LanceDB vector similarity** (B1), **Arrow → JupyterHub/polars EDA** (B1.8). Validated on a real run: `scripts/query_datasets_formats.py` reads **all 4 lakeFS formats (Parquet/Arrow/Avro/Lance) through one polars pass** (114k rows each). Fixes made closing it: the script's arrow reader (fsspec→bytes-via-s3fs) + lance reader (current pylance needs object_store `aws_`-prefixed keys, else anonymous→403); and a **`lakefs-lan` NodePort** (`192.168.1.243:30800`, mirrors mlflow-lan) so LAN clients reach the lakeFS S3 gateway with **no port-forward**.
- **B74** — **Hybrid retrieval (BM25 + dense fusion) in the tool-server** — ✂️ **CLOSED 2026-08-05 — premise overturned.** The B96 golden-set eval (run-7) showed dense retrieval (bge-base 768 + topic-prefix) **wins even on identifier-heavy queries**, so BM25 fusion isn't the win it was hypothesized to be. The `weyland_chunks` lexical index stays built + cataloged (harmless), but fusion won't be pursued — if a future query class stumps dense, solve it fresh there rather than carry a stale floating initiative. Historical scope: value-realization of the OpenSearch BM25 work: the lexical index (`weyland_chunks`) is built + cataloged but the RAG still queries dense-only; fuse BM25 + a vector backend (RRF) in the tool-server retrieval so lexical recall (exact identifiers/config keys/commands) joins semantic recall. Validate hybrid-vs-dense on the B4 eval leaderboard; feeds B70. See detail below.
- **B77** — **Data-quality layer: asset-checks / Great Expectations → DataHub Assertions** — ✅ **DONE 2026-08-06 — the DQ layer is complete: three sources (asset-check gate · Soda marts+silver · GE profiling) all surfacing to DataHub Assertions; GE Data Docs at ge-docs.weyland.lab; DoD swept (arch §7d · `flow-great-expectations` · LikeC4 · platform-map · demo `great-expectations.md` · hosts · drift-guard 74/green). Was 🔴 HIGH, promoted in the rebalance.** **Part (a)→DataHub SHIPPED 2026-08-06 (image v22):** `emit_asset_check_assertions()` surfaces the already-built `@asset_check` GATE as **184 per-silver-table DataHub Assertions** (`no_error_non_empty` from `detail` + `valid_column_names` from `schemas`, mapped to `trino:iceberg.datasets_<domain>.<ice_ident>` and `graph.exists`-guarded so a URN miss emits nothing) — wired into `datahub_catalog_emit_job` + a standalone `datahub_asset_check_assertions_job` for fast re-emit/verify. This is the **B80 unblocker**: assertion coverage jumps ~16 (Soda-only) → ~108 data-mesh silver datasets — exactly B80's target set. **UI-verified 2026-08-06** (371 total assertions, +184; `iceberg.datasets_music.fma_genres` Assertions tab green — `no_error_non_empty` + `valid_column_names`, SUCCESS). Op reads `context.instance` (user-code pod has no `$DAGSTER_HOME`). **Enrich (v23, 2026-08-06):** switched the read from the iceberg asset → the **parquet** asset (every table) + row/col-count metadata. **Finding — "brfss empty" was a RED HERRING, not a coverage gap** (my misread): plain `brfss` / `usda_fooddata` are **stale folder-named duplicates** from the June folder→per-file naming transition (`writers.ice_ident`); their live per-file twins (`brfss_brfss_2020` = `ASSERTIONS: PASS`, `usda_fooddata_*`) already carry passing assertions with the **identical schema**. Coverage is bounded by the `graph.exists` iceberg-URN anchor (parquet-vs-iceberg read doesn't change it) — current tables are **fully covered** (184). **Catalog hygiene DONE 2026-08-06:** soft-deleted **14 stale folder-named orphans** from the June folder→per-file naming transition — 4 old `iceberg.datasets.*` schema (fma_echonest/genres/tracks + spotify_tracks) + 9 health shorts (brfss, usda_fooddata, big_five, cdc_physical_activity, who_gho_{alcohol,diabetes,obesity,tobacco,mental_health}) + musicbrainz_artist — via `Status(removed=true)` (same mechanism as the opensearch/timescale ghost cleanup); verified gone (search excludes them, live per-file twins intact). Identification: no assertions = not in the current produced set. One-time (naming is stable); a durable emit-side reconcile (diff cataloged-vs-produced) is available if we ever want it self-maintaining. **All-null-columns check (v24/v25, 2026-08-06):** the transform now records per-column null counts (`broker.py` → `nulls` metadata) → a `no_all_null_columns` gate (WARN) + DataHub assertion catch a 100%-null column (the fma-URL / spotify-empty parse-failure class). Assertion count 184→**231** (+47 tables that carry null-bearing columns). **Triage: all 17 flagged health tables benign** — WHO GHO fixed-schema unused `Dim*`/`DataSourceDim`/`Comments`/`High`/`Low` slots, NHANES `BMIHEAD` (infant-only), NHIS edit/coverage flags, USDA `footnote`/`max_value` + `fdc_id_of_input_food` (verified via Trino: 18,584 rows, inputs referenced by `sr_code`/`sr_description`, not the FDC FK). A source-scoped `ALL_NULL_ALLOWLIST` (`checks.py`, shared by the emit) quiets these so a NEW all-null column reads as a real regression. **B77 lightweight `@asset_check` layer = DONE** — 3 checks/silver-table (`no_error_non_empty` · `valid_column_names` · `no_all_null_columns`); GE (part b) is the sole remaining thread (knowingly diminishing returns on static at-rest data). Also fixed: `soda-venv` Dockerfile `pip>=25` (was segfaulting on cache-miss). **Soda-to-silver (v26/v27, 2026-08-06 — the DQ-capability half):** extended the L5 Soda DQ from the 16 marts to the **silver** datasets — `music_silver.yml` (spotify audio-feature bounds 0–1, lastfm, gtzan) + enriched `health_gold.yml` (WHO GHO `numericvalue` bounds + big_five IPIP 0–5), wired into the `weyland_music`/`weyland_health` scans; results flow via the existing `emit_soda_assertions` → DataHub. **Posture:** marts stay **strict** (job fails on a mart contract violation); silver findings are **advisory** — emitted as failing assertions to the datasets' DataHub Quality tabs + a WARN log, but they do NOT fail the pipeline (source-data dirt we don't control; `soda_scan_op` raises only when the `weyland` marts scan fails). First run surfaced **3 real findings**: spotify `duration_ms=0` (placeholder track), lastfm age `−1337` & `1002` (leet/bogus self-reported ages). **GE (part b) DONE 2026-08-06 (the showcase half):** isolated `/opt/ge-venv` (GE 0.18 + trino + SA 1.4 — acryl-datahub 1.7 dropped the native GE action, so the emit is **hand-rolled** `emit_ge_assertions`, mirroring Soda). On-demand `ge_validate_job` → Fluent Trino **table** assets → **UserConfigurableProfiler** auto-profiles a per-column suite → checkpoint validates → Data Docs. **339 DataHub Assertions** across 3 showcase tables (mart_country_health 80 / mart_spotify_audio 106 / spotify_tracks 153 — GE **alongside** Soda + `@asset_check`, one pane). Data Docs served at **ge-docs.weyland.lab** (new nginx `ge-docs` app: PVC ← user-code GE write via DefaultRunLauncher-in-pod, forward-auth, `GeDocsDown` alert; registered in `applications.yaml` as a pure-compute `ui` component per the new DoD onboarding rule — Port/Kuma/alert). Gotchas: GE 0.18 **query** assets → table-level only (2 exp); **table asset + UserConfigurableProfiler** = the rich profile. Data Docs nest under `gx/` (nginx root). Auto-profiler bounds run tight (2/3 checkpoints fail — expected GE artifact; **advisory**, never fails the job). **B77 = the DQ layer is COMPLETE** — three sources (asset-check gate · Soda marts+silver · GE profiling) all surfacing to DataHub Assertions. **Remaining:** part (a) enrich (per-dataset non-null / row-count / schema checks → more assertions) + part (b) **GE suites** (the heavy auto-profiling/drift tail, now unblocked by B79). Incremental over the shipped Soda L5 DQ — value is fail-at-ingestion (`@asset_check`) + DataHub-Assertions surfacing vs Soda's after-the-fact scan. — move data-quality *detection* upstream instead of discovering it as a crash three layers down (the `fma_tracks` URL-as-column-name was found by crashing the Lance writer; spotify's empty column by an avro-manifest failure). Note the split: *cleaning* (the `sanitize_columns` name-normalize + `coerce_null_cols` null-cast in `datasets_lib`) stays in the transform — GE/checks **validate**, they don't mutate. Start with Dagster-native `@asset_check` (schema / non-null / column-name-pattern expectations on the silver assets), graduate to **Great Expectations** suites for richer/reusable checks; emit results to **DataHub Assertions** (GE has a native DataHub action) for one-pane governance + Alertmanager/Telegram alerting. Build as a `build_asset_checks(cfg)` factory in `datasets_lib`, mirroring `build_transform_assets(cfg)` — every domain gets checks for free from the explicit `DomainConfig`. Slots into **B1.6** governance (alongside Soda DQ). GE confirmed on the roadmap. **SPLIT (2026-06-30):** (a) **native Dagster `@asset_check` layer = the pre-hydration GATE, done BEFORE data-store-mageddon** — validate the silver/gold before fanning data into a dozen stores (catch the bad-schema class once, not per-store); (b) the heavier **Great Expectations suites → DataHub Assertions** governance/alerting = the later tail, rides with/after hydration. So three `datasets_lib` factories on one `DomainConfig`: `build_transform_assets` → `build_asset_checks` → `build_store_load_assets`. **SEQUENCING (2026-07-11, user):** the GE suites (part b) are a **maturity item scheduled AFTER B79** (Ollama→rogueone frees the RAM/node headroom GE's Python runner needs). GE is more *capable* (auto-profiling, ~300 expectations incl. KL-drift/JSON-schema, multi-backend) but heavy to operate and its edge is largely wasted on at-rest Trino data — so the **interim coverage (B80) is dbt-tests + Soda**: full DQ over every SQL-tabular dataset (~78% of the catalog; the rest is non-tabular grafana/dagster/graph/stream/vector where row-level assertions don't apply). GE revisited for auto-profiling/drift once the node can host it.
- **B78** — **Data-mesh maturity (bucket)** — 🔴 **HIGH (↑ Medium→High 2026-08-11 rebalance; B81 folded in [High — floored to parent 2026-08-13], B113 folded in [High, EMA-110]).** Three polish/expansion threads on the built mesh: **(a)** OFF → vector hydration (below); **(b)** the **JupyterHub notebook library** [B81 — full scope in its entry]; **(c)** a **financial/economic datasets domain** [B113 — full scope in its entry]. DataHub maturity (B80) + DQ (B77) stay their own buckets. — **(a) Open Food Facts → vector stores (Qdrant/Weaviate):** Deferred from the B1 vector-store hydration (2026-07-03): every other grid Qdrant/Weaviate=Y set went in one pass, but OFF is **~4.5M docs** → a full text-embed (`product_name`+`brands`+`categories_en` via bge-small) is *hours* on CPU and **~7 GB of vectors per store** (4.5M × 384 × 4B × 2) — not a lab footprint. Do it capped: filter to non-empty `product_name`, cap ~200k, embed the concatenated product text → ~600 MB/store, ~20–30 min. Reuses the `build_vector_load_assets` loader + `vector_spec` (`{text: [...], cap: 200000}`) already built for the other sets; just add the OFF spec + run. (Its nutrition columns are `large_string` in silver — string-parsed — so text similarity is the meaningful vector, not the nutrition numbers.)
- **B83** — **Flink streaming-processing tier (B1.5 streaming completion) — ✅ DONE 2026-07-13.** All 4 jobs live (RTA · CDC→lakehouse · Java DataStream health · PyFlink music) on the always-on `weyland-flink` session cluster; metrics ServiceMonitor + History Server UI validation + runbook `flink.md` / `flow-flink.md` diagram. Gotchas (avro classloader-relocation, Avro field CASE, `rpk --num 0` tails forever, History `/jobs/overview`) in [[flink-streaming-tier-b83]]. Flink→DataHub OpenLineage deferred (like dbt). Original design below. — the stream-processing engine over Redpanda that B1.5 deferred ("Flink stays on-demand, future target"). **Flink Kubernetes Operator** + one **always-on session cluster** (JobManager + 1 TaskManager, **sidecar OFF** like Redpanda/kafka-connect — dodges the Envoy long-connection stall [[neo4j-istio-bolt-longconn-stall]]), ns `data-mesh`, Flink 1.20; checkpoints → MinIO (RocksDB state backend). **Catalog keystone:** Flink's Iceberg connector on the SAME **Nessie** catalog as Trino/dbt → outputs land in `iceberg.*` (queryable in Trino/Superset, auto-cataloged by the DataHub iceberg source; reuses nessie-secret S3 creds). **4 jobs — every authoring surface:** (1) **RTA** — Flink SQL windowed agg on `datasets.music.lastfm` → Iceberg `analytics.trending_artists`; (2) **CDC → lakehouse** — Flink SQL on `cdc.musicbrainz.public.cdc_demo` (debezium format) → Iceberg **UPSERT** `datasets_music.cdc_demo_live`; (3) **Java DataStream (health)** — keyed stateful over `datasets.health.brfss` (per-state running risk) → topic `analytics.health.state_risk`; (4) **PyFlink (music)** — Python UDF over `datasets.music.lastfm`. Python↔music (DS/ML), Java↔health (robust/enterprise). SQL jobs = declarative **FlinkSessionJob SQL-runner** + a **SQL Gateway**; Argo GitOps `k8s/data-mesh/flink/`; UI `flink.weyland.lab` (forward-auth). RTA → Iceberg-only (live topic = easy later add). **KEDA scale-to-zero = later** ("we can KEDA-fy it later"). Runbook `flink.md` + `flow-flink.md` diagram; Flink→DataHub OpenLineage deferred (like dbt was). Design agreed 2026-07-13.
- **B82** — **Application taxonomy (cross-surface app classification)** — ✅ **DONE 2026-08-05; nested under B80.** DataHub emit `(29, 4157)`, 54 Port components (29 data-app / 25 pure-compute) each with `is_data_application` + DataHub link + a `capabilities` array, Argo-completeness check green (72 apps accounted). Enrichment live: Documentation link, group Tag, Domain, customProperties, + a 30-term **Application Capabilities** glossary (DataHub terms on the 29; the same capabilities as a Port array on all 54). Registry = `services/weyland-dagster/weyland_pipeline/applications.yaml`; DataHub `emit_applications()` + `tofu/port/applications.tf` (for_each) + `scripts/check-app-registry.sh` (drift guard). **DoD COMPLETE:** arch §7f · `concepts/application-catalog.md` · `flow-application-taxonomy` · LikeC4 · platform-map · demo (RUN, eyes-on) · drift guard. Follow-up (non-blocking): point `emit_applications` at the registry `capabilities` to retire the mirrored `_APP_CAPABILITIES` on the next Dagster rebuild. **Gate PASSED** — `acryl-datahub 1.6.0.15` / GMS v1.6.0 model the `Application` entity (`ApplicationPropertiesClass`/`ApplicationsClass` import clean). **Scope grew beyond DataHub into a cross-surface taxonomy** (the DoD's new "one source of truth" process): adopt DataHub's **Application** entity as an app-centric lens *alongside* Domains + Data Products, but the same app-classification lines must hold across **four surfaces — DataHub · Port · docs · diagrams — with zero drift.** The line: an app is a DataHub Application iff it **owns cataloged data now OR plausibly will** (→ DataHub Application **+** Port component, linked); pure-compute (KEDA scaler, TTS, stateless proxies, query engines) is **Port-component-only**. **Mechanism = one canonical registry** `services/weyland-dagster/weyland_pipeline/applications.yaml` (baked into the Dagster image + read by Tofu) that `datahub_emit.py`, `tofu/port/applications.tf`, and the docs/diagrams all consume or are DoD-checked against. **Final categorization: 29 DataHub Applications + 25 pure-compute = 54 components** (reclassified during the Argo-driven roster pass: grafana → data-app [owns ~367 grafana datasets], nessie + lakefs added as data-apps [cataloged DBs], ranger confirmed operational data-app; the earlier "~26 + borderline" framing is superseded). **Port is a first-class part of this body of work — not an afterthought.** Producer-based URN rules (mirror `_DOMAIN_RULES`); MLflow agent-traces attach by explicit tag. Design + full roster: `aidlc-docs/application-taxonomy.md`. Build sequence: registry → `emit_applications()` → Port codification → docs (`arch.md` + `concepts/application-catalog.md`) → LikeC4 + platform-map → DoD sweep. Relates B80 (umbrella), B43/B60 (Port), the DataHub governance layer.
- **B81** — **JupyterHub notebook library (B1.8 follow-on)** — ✂️ **FOLDED INTO B78 (2026-08-05)** — thread (b) of the data-mesh maturity bucket. Full scope retained here: grow the single seed notebook (`datasets_lake.ipynb` — 4 formats + polars/DuckDB, done 2026-07-12) into a **semi-exhaustive, runnable library of notebooks demonstrating the whole data/ml/ai stack**, baked into (or git-synced to) the JupyterHub singleuser image so opening JupyterLab is a real, self-documenting playground. **(a) Per-format deep dives** — one notebook EACH for **Parquet · Arrow/IPC · Avro · Lance**: format internals (columnar vs row, encoding/compression, zero-copy for Arrow, dataset versioning + vector-index for Lance, schema evolution for Avro), read/write, and when-to-use — beyond the one combined datasets_lake notebook. **(b) Full-stack library** — a curated set spanning every layer: **storage/versioning** (lakeFS branching, Nessie/Iceberg time-travel + snapshots); **query/federation** (Trino cross-catalog, DuckDB/GizmoSQL, + one per Tier-2 store: ClickHouse/Cassandra/MySQL/Mongo/Cockroach/Timescale); **vector/graph** (Qdrant/Weaviate/Lance similarity search, Neo4j Cypher); **transform/semantic** (dbt marts, MetricFlow `mf query`, Cube REST/SQL); **feature/ML** (Feast online + point-in-time retrieval, Ray training/HP-sweep submission → MLflow tracking/registry); **AI/RAG** (LlamaIndex retrieval over the vector stores, embeddings, the eval harness, LiteLLM/Ollama); **governance/quality** (DataHub lineage/GraphQL queries, Soda scans, Ranger-masked queries); **streaming** (Redpanda consume, Debezium CDC tail). **Distribution:** notebooks live in the repo (`k8s/jupyterhub/singleuser/notebooks/`); consider **nbgitpuller / git-sync** so the library updates without an image rebuild (the current `cp -n /opt/examples` postStart is fine for one seed but doesn't scale). Each notebook doubles as a living demo + doc of that layer. See runbooks/jupyterhub.md, [[cube-semantic-layer-b1.7]].
- **B113** — **Financial / economic datasets domain (data-mesh)** — ✂️ **FOLDED INTO B78 (2026-08-05)** — thread (c) of the data-mesh maturity bucket. Full scope retained here: extend the datasets-lake beyond health/music to a **financial + economic** domain, ingested + maintained the SAME way (a `DomainConfig` → `build_transform_assets` → `build_asset_checks` → `build_store_load_assets` → silver/gold Iceberg → Trino / DataHub / Tier-2 stores; the agents reach it via the existing `trino` / `datahub` fleet MCPs — **no paid third-party MCP** like Bigdata.com/RavenPack). **Free sources:** **SEC EDGAR** (company filings + XBRL company-facts API, free, no key), **FRED** (Federal Reserve economic series, free API key), **Alpha Vantage** / **Finnhub** (market/equity data, free tiers). Static snapshots into the mesh like every other dataset; **optional** later: a small scheduled live-refresh or a tiny self-built MCP if *currency* (today's filings/prices/news) is wanted — the free APIs above beat a paid institutional feed. Decided 2026-07-31 (vs Bigdata.com): self-host the open data, skip the enterprise vendor. Relates B1 (data mesh), B77 (DQ `@asset_check`/GE), B73 (dataset uses), B80.
- **B114** — **Stud.IO → Figma design system (code → design)** — ✂️ **FOLDED INTO B39 (2026-08-05)** — the code→design half of the Figma↔code workflow bucket. Full scope: extract Stud.IO's UI into a **Figma design system** and manage the experience there, keeping it linked back to code. Bidirectional via the **official Figma MCP** (the Claude Code `figma` plugin — **not** a Bifrost MCP-library install; that entry is agent read-context only): **`figma-generate-library`** discovers Stud.IO's components + design tokens *from the codebase* and builds the Figma library; **`figma-generate-design`** assembles the pages/screens in Figma; **Code Connect** (`figma-code-connect`) maps Figma components ↔ Stud.IO code so design and code stay in sync as UX is managed in Figma. An interactive Claude Code workflow (point it at the Stud.IO repo), not a standing agent tool. Relates **B46** (Stud.io product backlog).
- **B116** — **chat.weyland.lab (Open WebUI) workspace review** — 🔴 **HIGH (2026-08-05 — promoted; active user-facing surface).** go through the Open WebUI workspace end-to-end and curate it into a coherent lab assistant rather than a raw model list: **model connections** (Ollama native + the B115 `nemo-guardrails` guarded `weyland-operator` lane — incl. why a new OpenAI-connection model may not surface without an admin-panel refresh / per-user model visibility), **personas / system prompts**, the **prompt library**, **tools / functions**, **RAG / knowledge** collections, **voice** (STT whisper shim + a TTS lane, e.g. Kokoro), **users / RBAC + Keycloak SSO** defaults, and general **UX / settings**. Prompted 2026-08-03 while wiring the B115 Dialog guarded model (the guarded lane didn't appear in the picker — a workspace-config gap, not just the connection). Relates B13 (Open WebUI), B115 (guardrails Dialog).
- **B117** — **weyland-guard scanner modernization (retire LLM Guard)** — the Scan layer's three `llm_guard.*` validators (injection · toxicity · PII) run on **protectai/llm-guard**, whose maintenance cadence dropped after the Palo Alto acquisition (repo not dead — PRs into late-2025, docs 2026 — but slowed; the replacements are purpose-built + better-maintained regardless). Swap to actively-maintained tools — and it **consolidates rather than adds**: (1) **PII → Microsoft Presidio** called directly (near drop-in — llm-guard's `Sensitive` scanner already *just wraps* Presidio, B34; Presidio is MIT + actively released through 2026); (2) **injection → Meta Llama Prompt Guard 2** (86M/22M classifier, served via llama.cpp — same pattern as the B115 Llama Guard, its injection sibling); (3) **toxicity → folded into Llama Guard** (its unsafe S-categories already cover hate/harassment/sexual/etc. — drop a separate scanner; **decided 2026-08-04, option A** over Detoxify [stagnant] / Guardrails-AI toxic [LLM-backed, slower]). Net: **drop the llm-guard dependency entirely**; the three capabilities land on the **Meta guard family (Prompt Guard + Llama Guard) + Presidio**, all actively maintained + mostly already deployed. Retire `guardrails/validators/llm_guard.py`; new `prompt_guard` + `pii_presidio` validators; all land in **SHADOW** first (measure FP on real traffic before enforcing), like the originals. Design: `aidlc-docs/guard-scanner-modernization.md`. Relates B115 (Scan/Classify), B34 (PII), B35 (grounding), B14 (guards). **✅ BUILT + VALIDATED + DoD-SWEPT 2026-08-05 (SHADOW).** Guard image **v10**: `prompt_guard.injection` (Prompt Guard 2 — a DeBERTa *encoder classifier*, NOT llama.cpp-servable, so it runs **in-process** like the grounding CrossEncoder, not as a service — corrected mid-build) + `pii.presidio` (Presidio direct) live; `llm_guard.py` + the `llm-guard` dep **removed**; toxicity folded into `llama_guard.safety`. **Validation (direct `.check()`):** injection → BLOCK @ 0.998 / benign → PASS @ 0.001; email+SSN answer → BLOCK @ 1.0 (EMAIL_ADDRESS) / clean → PASS. DoD swept (arch/api/concepts/platform-map/likec4 + flow-guardrails + runbook + demo). **Remaining before "done":** measure the new validators' FP rate on a clean day of `guardrail_verdicts` before any SHADOW→`block` promotion.
- **B118** — **Stud.IO code-quality / CI: DeepSource + CodeScene + the 2nd Woodpecker track** — ✅ **DONE 2026-08-19 [Linear EMA-107, under B57/EMA-46].** **Found already ~live** — the review stack was running on the public `edtbl76/stud.io` repo (STUD.io carried its own `.deepsource.toml`/`.coderabbit.yaml`/`.pr_agent.toml`/`.mcp.json` predating B106). **Verified on stud.io PR #121** (`gh pr checks`): **DeepSource** (7 analyzers), **CodeScene** (Code Health Review, project 78184), and **Sourcery** post checks; **CodeRabbit** + **Qodo Merge** review in the conversation. The **2nd Woodpecker track → Port CI signal** landed in **B63** (`ci_pipeline` → `weyland_ci_reliability`, stud.io #14/#15). **Full-parity close-out shipped:** STUD.io repo `docs/arch/code-review-stack.md` (new) + reconciled stale docs (`workflow.md` said CodeScene "not a CI gate" — it is; `github.md` said "two AI reviewers" — it's five); weyland `applications.yaml` code-review entries + the 6 Port `component` entities updated to cover **both** public repos (weyland-lab + stud.io); weyland `runbooks/code-review-stack.md` gained a STUD.io-parity section. **Greptile is installed too** (App access confirmed across weyland-lab + stud.io + emangini-tailwind) — it reviews via a PR comment (not a check-run) and wasn't observed on the recent Dependabot PRs; confirm on the next human PR. So the full stack is present on stud.io. Docs: [runbooks/code-review-stack.md](runbooks/code-review-stack.md) · [diagrams/flow-studio-code-review.md](diagrams/flow-studio-code-review.md) · [demos/studio-code-review.md](demos/studio-code-review.md). **Original scope (for the record):** part of the Stud.IO cluster (with B46 product backlog + B39 Figma workflow). Add **DeepSource** (automated static analysis + autofix PRs) + **CodeScene** (behavioral code-health — hotspots, tech-debt, knowledge-map; complements the existing code-maat hotspots) to the code-quality suite (alongside SonarQube/Trivy/Semgrep). Wire the **other Woodpecker track** (Stud.IO's test/prod CI pipeline, per the B46 seed) so its runs feed the Port CI signal + DORA deployment-frequency. Feeds the Port **Code Health** dashboard + Stud.IO. Scope: **Stud.IO-first.** **Scope expanded by the B106 decision (2026-08-08)** → this now wires the **CI/repo side of the adopted 7-tool stack:** DeepSource (Autofix PRs + Port `security_scan`/`code_quality` feed), CodeScene (CI), **PR-Agent** (self-hosted via LiteLLM/Bifrost — Action/CLI), **Greptile** (PR-native, once a PR flow exists); **Sourcery + Continue are IDE-side installs** (out of B118's CI scope). $0 check **resolved** — all free OSS/public-repo or self-host. Paid **Qodo cancelled**; **CodeRabbit** kept on the free tier. Relates B106 (the eval), B47 (code-quality triage), B56 (Woodpecker), B60 (Port), B46/B39 (Stud.IO).
- **B119** — **Linear feature evaluation (master the tool)** — 🟡 **MEDIUM (2026-08-05).** Go through **Linear** end-to-end and evaluate all of its additional/underused features against the lab's workflow — the same "master the tool" pass done for Port (B60) and DataHub (B80). Candidate surfaces to walk: **Projects / Milestones**, **Cycles** (sprints), **Initiatives**, **Roadmaps**, **Triage**, **sub-issues / dependencies / relations**, **labels & label groups**, **custom views / filters / saved searches**, **SLAs**, **estimates** (the estimate-as-rank convention), **workflows / statuses**, **automations & rules**, **integrations** (GitHub/Slack/Port), the **Linear MCP + agent** surface, **documents**, **releases**, **insights / analytics**, and **API/webhooks**. Output = a decision on which features to actually adopt for the weyland roadmap (Linear = the working/reasoning surface; `backlog.md` = the durable record). Relates B43/B60 (Port IDP), the Linear-sync convention. **$0** (existing free tier).
- **B80** — **DataHub maturity (umbrella)** — ✅ **DONE 2026-08-06 (image v32).** The governance surface is closed. **(1) Contracts mesh-wide** — reworked `emit_data_contracts` from per-mart Soda-only to a **source-agnostic per-dataset** contract that queries DataHub for the dataset's full assertion set (Soda + `@asset_check` + GE) and bundles it ACTIVE (~102 data-mesh datasets, decoupled from the Soda path into `datahub_catalog_emit_job`). **(2) Siblings merge** — `emit_siblings` links each logical table's up-to-3 platform twins (`trino:iceberg.<s>.<t>` where governance lives + the `dbt:` and `iceberg:` twins users land on) via the `Siblings` aspect (126 groups, primary = trino), so governance is visible on whichever entity you open. **(3) Stats-wide** — the already-built `_emit_profile` (rowCount `DatasetProfile`) on all recipe-less stores lifted Stats to **2995/3756 (79%) = ~95% of every *profileable* dataset**; every custom store 100% (qdrant/weaviate/lancedb/opensearch/duckdb 112 /mysql/cockroach), the ~615 uncovered genuinely non-tabular (grafana 373 pseudo · dagster 97 · s3/parquet/arrow/avro/lance ~100 · neo4j 26 · kafka 4 · mongo 10). **KEY GOTCHA (proven via eyes-on UAT):** DataHub's sibling merge covers the **Assertions** tab but resolves the **Data Contract** tab + **Stats** *strictly per-URN* — so contracts are emitted on **every twin** to stay visible where users land (the iceberg twin showed "No contract found" until v32). **DoD swept:** arch §7d · demo `datahub-maturity.md` (inline sequence) · demos README E5 · backlog. B82 (Application taxonomy) folded in ✅. All governance surfaces at their honest ceilings; mechanism end-to-end via `datahub_emit.py`. (Was 🔴 HIGH, blocked-by-B77 → resumable → done.) All own-scope surfaces are at their honest ceilings — Domains/Owners 100% · dataset Tags 100% + field-tags 2647 · Terms+descriptions 76% (rest unmappable) · **Stats 73%** (rest genuinely non-stats) · **Applications = B82 ✅**; mechanism proven end-to-end via `datahub_emit.py` → `datahub_catalog_emit_job`. **The one remaining thread — Assertions / Data-Contracts BREADTH — is gated on B77:** you can only emit an assertion for a dataset that has a *check*, and producing checks (`@asset_check` / GE → DataHub Assertions) is B77's scope. B80 cannot progress that thread until B77 lands upstream, so it stays OPEN-BLOCKED (not closed) pending B77. (Promoted HIGH in the rebalance; B82 folded in.) (2026-08-05: **B82 folded in** — the DataHub-maturity efforts collapsed into one item.) Covers **(a) completeness/Stats** (below); **(b) Application entities** [from B82: group assets by the owning app/service — `tool-server`, `weyland-dagster`, `genre-classifier`, `cube`, `feast-server` — git-emitted via `datahub_emit.py` into `datahub_catalog_emit_job`; verify the Application entity type exists in the running DataHub (v1.6.0) before scoping — newer feature]; **(c)** other governance-surface hardening. — Completeness detail: the catalog has datasets but is thin on governance surfaces. Cluster-wide reality (recon 2026-07-11): **3255 datasets**, but ~75% is OPERATIONAL app data (**postgres 2076** = GlitchTip issue/event/span/trace, Uptime-Kuma monitor/is_up, Keycloak, Lightdash, Unleash, SonarQube; **grafana 367**); the actual DATA-MESH datasets are the minority (trino 127 + iceberg 120 + dbt 23 + the Tier-2 store copies + vectors/graph). **SCOPE DECISION (open):** does the full treatment apply to the operational majority, or is the target the ~few-hundred data-mesh datasets? Operational internals (span_id/trace_id/issue_id/monitor_id) are a poor fit for data-mesh governance. Status per surface (coverage = datasets actually populated / 3255):
    - **✅ Domains** — 3255/3255, **0 domainless** (`emit_domains` fallback: business data → its domain, everything else → Platform & Ops). CAVEAT: 2443 land on the Platform & Ops fallback (defensible — infra IS ops).
    - **✅ Owners** — 3255/3255 (`emit_ownership`: CorpGroup `weyland` = Technical Owner).
    - **✅ Tags (#1/#3)** — **dataset tags 3282/3282 (100%)** (from 753) + **field tags on 2647 datasets** (identifier 2423 / temporal 1525 / measure 735, from 0). `emit_tags` materializes 31 tag entities (medallion + store-tier + source-system mirrored from the structured-property vocabulary + the field-class tags); `emit_tag_assignments` applies **layer + store-tier + source** to every dataset by URN pattern (read-merge, reusing `_infer_layer`/`_STORE_TIER_BY_PLATFORM`/`_infer_source`); `emit_mesh_glossary` now also attaches **field-level** identifier/temporal/measure tags in the same walk. (bronze/raw layers absent = raw MinIO isn't cataloged as datasets.)
    - **✅ Field terms/desc (#3/#6)** — **2478/3256 (76%)** now have ≥1 glossary term **and** a field description (up from 917/28% and ~0). `mesh_vocabulary` grew to 89 terms incl. a common-technical + observability cluster (id/name/timestamp/created_at + Sentry span_id/trace_id/issue_id/event_id + Kuma monitor_id/is_up/response_time); `emit_mesh_glossary` now also fills each field's **description** from the term definition (never clobbering the dbt marts) → 12,390 field-attaches across 2478 datasets. Remaining ~24% is mostly grafana pseudo-datasets + genuinely unmappable columns. Field-level **tags** still open.
    - **◐ Stats (#7)** — **2388/3262 (73%)**, up from 16. Two paths: (a) **ingestion table-level profiling** (`profile_table_level_only: true`) enabled in the postgres/clickhouse/musicbrainz recipes → postgres 2056, clickhouse 56, cassandra 10; (b) **custom-emit `DatasetProfile`** (rowCount) added to the 7 custom store emitters (`_emit_profile` helper + emit_qdrant/weaviate/lancedb/opensearch/duckdb/mysql/timescaledb) → duckdb 112, mysql 32, weaviate/qdrant/lancedb full, opensearch/timescale full-of-live. **cockroachdb 9/9** via a custom-emit `emit_cockroachdb_profiles` (the `cockroachdb` ingestion profiler emits NO DatasetProfile despite `profiling` enabled — bypassed it, psycopg2 count per db-per-dataset brfss/nhis). iceberg profiling reverted (`profile_table_level_only` rejected by IcebergSourceConfig — Soda covers marts+gold on trino URNs); mongo (source rejects `profiling`). Genuinely non-stats (~630, accepted): grafana/dagster/s3/neo4j/dbt/parquet/arrow/avro/lance/kafka/lakefs. Also surfaced: **stale catalog entries** (opensearch 19, timescale 8 = datasets whose store objects were dropped) → soft-delete cleanup, separate.
    - **✗ Data Contracts (#5)** — 16/3255 (`emit_data_contracts`, per mart/gold, referencing Soda assertions). Curated-per-table; real target = the data products, pending the scope call. **Not done.**
    - **✗ Queries (#4)** — 7/3255 (`emit_queries`, one canonical example per mart). **Not done** beyond marts.
    - **✗ Assertions (#8)** — 16/3255 (Soda marts + WHO/BRFSS gold; emitters are now **schema-aware** so more schemas can be added — enabler done, coverage not). **Not done.**
  Mechanism proven end-to-end (schema-aware Soda emit → assertions/profiles/contracts; git-emitted domains/owners/tags/terms/queries in `datahub_emit.py` → `datahub_catalog_emit_job`); the gap is **breadth**. Next: settle the operational-vs-mesh scope, then (a) ingestion-source profiling for Stats breadth, (b) a field-**description** "define once" map alongside the glossary, (c) decide the assertion/contract target set. Relates to **B77** (upstream `@asset_check`/GE → DataHub Assertions).
- **B47** — **Code-quality findings triage** — ✅ **DONE 2026-08-07 (scan-suite v4).** Residual triage closed: the tool-server `urllib` health-check FP (dynamic-urllib/SSRF on `_check_qdrant`/`_check_weaviate`, `main.py:348/358`) is suppressed with a bare `# nosemgrep` + a WHY comment (internal health-checks, URL built from trusted in-cluster env constants, never user input); fresh re-scan run; the accepted residuals (`.trivyignore` KSV/ranger, osv phantoms) still hold. The **docs-reconciliation grew into a full capability** — weyland-as-build-suite-home + a `quality-tools.yaml` registry + 8 new Stud.IO tools — split out as **B120**. (Was 🔴 HIGH, promoted; fed the Stud.IO code-quality cluster.) _(Scoped 2026-08-05: ~90% subsumed by B89 — Dockerfile/KSV findings already accepted in `.trivyignore`, hermes findings moot; residual = document the tool-server `urllib` health-check false positive + a fresh re-scan.)_ One triage pass: suppress the phantom highs (`.trivyignore`/`osv-scanner.toml` — most scan-suite highs are false per [[code-quality-scan-triage]]), fix the handful of real ones, then it's maintenance. act on the first SonarQube/Trivy/Semgrep scans (don't let the scanners be stand-up-and-ignore). Known: 3 Dockerfiles missing `USER` (run as root — Trivy `DS-0002` + Semgrep, easy win), dynamic `urllib` in `tool-server/main.py` + `hermes/roadmap-sync.py`, H2C smuggling in `hermes/dashboard-nginx.conf`, tool-server Deployment misconfig (KSV-0118). Low-risk on a LAN-only lab but real hardening. Re-scan after fixes (entities update in Port).
- **B120** — **weyland = the build-suite home: multi-language scan-suite + quality-tools registry** — ✅ **DONE 2026-08-07 (scan-suite v4).** weyland now houses the code-quality/security build suite going forward, so the suite is **multi-language** and its toolset is a **canonical registry**. **(1) Registry `quality-tools.yaml`** (repo root) — SOURCE OF TRUTH for all 22 quality tools (19 scan-suite + SonarQube + DeepSource/CodeScene inventoried, `enabled:false`, `wired_by:B118`); the docs (tools/arch/runbook/flow/schedules) now **CITE** it instead of hand-listing (killed the "9 vs 10" drift by construction), guarded by `scripts/check-quality-tools.sh` (19/19 green). **(2) +8 tools** wired into `scan.py` from the Stud.IO toolset: **ruff** (Python lint/format — 76 findings on the previously-unlinted 2029 `.py`), **pip-audit** (Python dep CVEs, 35H — 2nd engine next to osv's 41H), **detect-secrets** (3rd secrets engine, sealed-secrets excluded → 0 flood), **headers** (NOVEL — live HTTP security-header probe of the ingress hosts in hosts.md; 38 reachable / 37 HTML / **12** missing-header findings), + the **Go trio + go-vet** (gosec/govulncheck/staticcheck — clean 0 no-op on weyland's 0-Go tree, run against polyglot repos like Stud.IO). **(3) Dockerfile** — pip (ruff/pip-audit/detect-secrets) + full Go toolchain (`go install` the trio). **DoD swept:** arch §7d-adjacent · runbook · `flow-code-quality` · schedules · tools.md all cite the registry; **Pillar 7 (Security & code-quality scan) added to `definition-of-done.md`** in the same batch. Verified end-to-end on `scan-suite:v4` — all 19 tools post to Port. **Follow-ups:** DeepSource+CodeScene wiring = **B118**; pointing the CronJob at OTHER repos (Stud.IO — the real payoff of the Go tools) = parameterize the clone target (small). Relates B47 (the triage it grew from), B118 (managed SAST), the Stud.IO cluster (B46/B39/B118), B82 (the registry-as-source-of-truth pattern).
- **B121** — **Cassandra loader progress markers (hydrate observability gap)** — ✅ **DONE 2026-08-07** (code; ships on the next user-code image — added a per-200k-row heartbeat + a "writing N rows" start line to `_load_dataset_to_cassandra`, loaders.py). The `datasets_*_cassandra_load` step runs **silent for 15-40 min** on the big writes (lastfm ~17M rows by user_id) — only `STEP_START`, then nothing until the step ends — so running-vs-wedged is indistinguishable without `kubectl top pod` (exactly the trap that made the 2026-08-07 music hydrate look hung). B105 added phase/embedding markers to the vector + SQL loaders (`_build_vectors`, cockroach per-table) but the **Cassandra loader was missed**. Add a per-N-rows / per-partition-batch `log.info("cassandra <ks>.<table>: N/M rows")` like the others carry. Cheap; closes the last silent step. Extends **B105**; [[cassandra-tier2-hydration]].
- **B122** — **GPU-offload the hydrate vector embedding** — ⛔ **WON'T DO 2026-08-07** — the premise doesn't hold: hydrates are **on-demand/manual, NOT scheduled** (static reference data; `schedules/__init__.py` line 33), so the ~2h is a rare operator-chosen run, not a recurring overnight cost. GPU-offload (a bge-small endpoint on rogueone + a CPU fallback for when the laptop sleeps) is over-engineering for a $0 single-user lab. Original rationale, kept for context: The music hydrate takes **~2h**; the dominant cost is embedding the 7 music vector datasets with **bge-small in-process on mother's CPU** (`_build_vectors` — e.g. audioset 35,824 texts plus larger sets), serialized behind the SQL loads at conc=2. rogueone already runs a warm GPU embed service (**`rag-embed`**, bge-base on the RTX 5000, `192.168.1.230:8900`) that the RAG stream uses — route the dataset `_build_vectors` encode through it (or the on-demand vLLM path) instead of grinding CPU. Tradeoff: cross-host dependency + rogueone must be awake; hydrates are overnight-scheduled so wall-clock is *less* critical → opportunistic, not urgent. [[vector-store-hydration-b1]], [[remote-training-rogueone]].
- **B123** — **Hydrate reliability hardening (2026-08-07 disk-stall incident)** — ✅ **DONE 2026-08-07** (all fixes shipped; residuals are deploy-time verifies, not open work). Consolidates the incident + its fixes. A Cockroach **Pebble fsync disk-stall** during the health hydrate → widening `storage.max_sync_duration` 20s→120s *removed the fail-fast*, and the unbounded-parallel hydrate + noon schedules then **saturated the single node** (97% mem, kubectl froze, k3s restart hung). **DONE this session:** schedules moved **overnight-only** ([schedules.md](schedules.md) Rule #5) · hydrate jobs capped **`max_concurrent=2`** · Cassandra `default_timeout` 60→**300s** · mother RAM **72→78Gi** + the store-park discipline ([runbooks/node-capacity.md](runbooks/node-capacity.md)) · Cockroach `max_sync_duration=40s`+`fatal.enabled` **codified durably** as a self-healing postStart hook in `cockroachdb.yaml` (was live-SQL-only → a PVC rebuild reverted it to the crash-prone default). **Residual:** (1) verify the postStart hook fires on the next cockroach roll; (2) a short incident postmortem doc; (3) note the opensearch health-hydrate hang was a **post-reboot shard-recovery wedge** (music's opensearch step completed clean), not a loader bug. [[node-oom-forensics]], [[clickhouse-tier2-hydration]].
- **B48** — **Observability: unified logs + traces in Grafana (Loki + Tempo)** — **DONE 2026-06-21.** Full LGTM: **Loki** (SingleBinary → MinIO) + **Alloy** DaemonSet (logs), **Tempo** (monolithic → MinIO, traces). Istio mesh tracing + Kiali repointed to Tempo; **Jaeger retired** (addon + ingress + datasource removed). Grafana Loki/Tempo datasources → Explore + Logs/Traces Drilldown. See [runbooks/observability.md](runbooks/observability.md) Phase 4. **Follow-up (B49).**
- **B49** — **Observability (bucket)** — ✅ **DONE 2026-08-08.** All 3 threads shipped + verified via grafana-mcp: **(a)** Tempo metrics-generator processors override → `traces_spanmetrics_*`/`traces_service_graph_*` for 26 services (registry_active_series 0→1247); **(b)** app-level OTel → Tempo OTLP for **tool-server** (FastAPI+httpx per-request; 2.4 spans/sec) + **Dagster** (`@traced_load` → per-dataset `<store>_load:<dataset>` coarse spans, e.g. `clickhouse_load:usda_fooddata`; `weyland_pipeline/_otel.py`) — `runbooks/observability.md` Phase 5; **(c)** grafana-mcp dashboard audit → pruned the orphaned **Jaeger** + deprecated **Alertmanager** datasources (5/5 healthy). Lessons baked into the docs: verify generator OUTPUT not config; kube-prometheus-stack auto-injects the AM datasource so `deleteDatasources` loses without `grafana.sidecar.datasources.alertmanager.enabled: false`; OTLP **HTTP not gRPC** on the meshed→unmeshed hop; **SimpleSpanProcessor** for Dagster's forking executor; keep Dagster spans COARSE (per-dataset) — never auto-instrument DB drivers (span explosion). Folds in **B54** (OTel app instr) + **B109** (dashboard audit). _(Was 🔴 HIGH; 2026-08-05.)_ Original threads: **(a) Tempo metrics-generator** (span-metrics + service-graph — fixes the empty Drilldown Rate/Error panels; below); **(b) OTel app instrumentation → Tempo** [B54 — real app-level spans from tool-server/Dagster]; **(c) Grafana dashboard audit** [B109 — dashboard hygiene, via grafana-mcp]. — **(a) Tempo metrics-generator:** the Drilldown Rate/Error overview panels show "empty ring" because Tempo's metrics-generator isn't enabled (needs Tempo→Prometheus remote-write: `metricsGenerator.enabled` + Prometheus `enableRemoteWriteReceiver`). Traces themselves work; this only adds the RED/service-graph panels. Optional polish. — **Progress 2026-08-08:** **(a) ✅ DONE + VERIFIED 2026-08-08** — my first "done" was wrong (marked on config, not output). Root-caused: the generator was enabled (B111) but had **0 active series** — the per-tenant **processors override was missing** (the chart does NOT default them despite the values comment; `/conf/overrides.yaml` rendered `{}`). Fix: added `tempo.overrides.defaults.metrics_generator.processors: [service-graphs, span-metrics, local-blocks]` (grafana/tempo 1.24.4 chart key, confirmed from the chart values). Post-roll verified via grafana-mcp: `registry_active_series` **0→1247**, and `traces_spanmetrics_*` + `traces_service_graph_*` now flow to Prometheus for **26 services** → the Drilldown Rate/Error panels + service-graph populate. Lesson: enabling the generator *component* is necessary-not-sufficient; the *processors* must be turned on too — verify the OUTPUT (`active_series`/`traces_spanmetrics_*`), not just the config. **(c) ✅ AUDIT RUN** via grafana-mcp (first real fleet-MCP application): 37 dashboards, 2 broken datasources found + fixed — **Jaeger** orphan (B48 removed it from config but Grafana provisioning is add-only → never pruned) + **Alertmanager** (Grafana 13 deprecated the standalone datasource, ships it plugin-disabled → "plugin unavailable"), both pruned via `grafana.deleteDatasources` (documented in the values note + `runbooks/observability.md` Phase 3; alerting→Telegram unaffected). Ray dashboards fine (`ray_*` metrics live; version tag cosmetic — no action, no item). Minor find: Grafana apiserver mis-dials Tempo `:3200` as gRPC (recurring log noise; the trace datasource works over HTTP). **Remaining: (b)** OTel app instrumentation → Tempo.
- **B50** — **Port as launcher (not status board)** — DONE 2026-06-21 (recording the model change). Retired the Kuma→Port `uptime_monitor` flow (status went stale — Kuma webhook is event-only); Port now = `endpoint` blueprint (31 entities) + **Launcher** dashboard (one-click UIs/APIs). Kuma (`kuma.weyland.lab`, Telegram paging) is the live status board. Catalog cruft left as-is (istio_gateway/VS empty, k8s_pod churn, DORA defaults) — deep-clean only if Port gets noisy.
- **B51** — **APM & Alerting** (batch — **DONE 2026-06-21**) — app-observability on top of LGTM. **DONE:** (1) **GlitchTip** self-hosted error tracking (web + worker + **Valkey** — required for the cache, `valkey://` scheme; meshed Postgres; `glitchtip.weyland.lab`; [runbooks/glitchtip.md](runbooks/glitchtip.md)) with **tool-server** (project 1) + **Dagster** (project 2) instrumented via the Sentry SDK (Dagster needs the `modules` integration disabled — its big dep tree bloats events past GlitchTip's size limit → 200-then-dropped); (5) **GlitchTip → Port** webhook (`glitchtip_issue` blueprint off the Slack-attachment payload) + GlitchTip in the Launcher + **registration locked** (`ENABLE_USER_REGISTRATION=false`); (4) **Loki ruler** LogQL alert rules → existing **Alertmanager → Telegram** (one alert pipeline for metrics + logs; rules ConfigMap mounted at `/rules/fake`, threshold tunable). **Deferred:** Hermes error tracking → **B52**; Sentry SaaS + OTel app instrumentation → **Extras** (B53/B54). **Skipped:** SigNoz (duplicates LGTM), self-hosted Sentry (too heavy).
- **B52** — **Hermes error tracking (GlitchTip)** — ⚰️ **MOOT 2026-07-23** (Hermes retired/destroyed — nothing to instrument; the B66 operator, being ours, wires GlitchTip directly like the tool-server). Historical: deferred from B51; Hermes is a **third-party packaged agent** (`NousResearch/hermes-agent`, no source of ours), so instrumentation = the **injection route**: install the **mkcert root CA into CT 104** (HTTPS to `glitchtip.weyland.lab`), `uv pip install sentry-sdk` into the gateway venv (`/usr/local/lib/hermes-agent/venv`), a `sitecustomize.py` that inits Sentry (with `modules` integration disabled — big dep tree), and `SENTRY_DSN` as a real env var in the `hermes-gateway` systemd unit. High effort / lower payoff for a 3rd-party agent with its own logging — revisit if Hermes starts erroring in a way worth tracking.
- **B55** — **Cloud Cost (OpenCost) + lab cost picture** (batch — **DONE 2026-06-22**) — the Port **Cloud Cost** category (B43 follow-on) plus a full lab-TCO view. **(1) OpenCost** (CNCF, ns `opencost`, `opencost.weyland.lab`) reads the existing kube-prometheus Prometheus; **custom on-prem pricing** (bare-metal MS-A2, no cloud bill): $2500/5yr ($41.67) + ~55W @ $0.16/kWh (Wilmington=RMLD, $6.42) = **~$48/mo box**, split 50/50 CPU:RAM over 32 vCPU/96GB → k3s slice ~$15/mo. [runbooks/opencost.md](runbooks/opencost.md). **(2) LiteLLM spend meter** — already wired by B26 (`callbacks:[prometheus]` + ServiceMonitor); closed the TODO — spend metric is **`litellm_spend_metric_total`**, scrape path → `/metrics/` (307 trailing-slash), spend alert now valid → Telegram. ~$0 (free tiers; Claude is a flat sub, NOT routed through LiteLLM). **(3) Port `cost` blueprint** — categorized (infra/ai/dev-tools/domain/business) + cadence-aware `monthlyCost` calc; seeded **Claude Max $200** + infra $48 + LiteLLM $0 = **~$248/mo** (Claude ≈ 80%); OpenCost in the Launcher; a **Cost dashboard** (total + table). B50-aligned: Port = summary + launcher, OpenCost = live detail. **Deferred (maturity):** the full **subscription dump** (JetBrains, emangini.com domain, other SaaS — the categorized ledger is ready to fill); optional Prometheus→Port live-LLM-spend push.
- **B56** — **CI/CD (Woodpecker) → Port** (batch — **DONE 2026-06-22**) — the Port **CI/CD** category (B43's last category → all categories now wired) + the lab's first build automation. **Woodpecker CI** on k3s (server + 2 agents, ns `woodpecker`, `woodpecker.weyland.lab`, GitHub OAuth, SQLite) with the **kubernetes backend** — pipeline steps run as **pods in-cluster** (so pipelines can build/deploy the weyland apps). **LAN-only:** GitHub can't reach the lab for push webhooks → triggers are **manual / cron** (same wall as B30). First `.woodpecker.yml` (info + yamllint via a `.yamllint` = relaxed minus line-length) proves the backend; a `notify-port` step POSTs build status → Port **`ci_pipeline`** blueprint (id `repo-number`, history per run) via a Woodpecker repo secret `port_ingest_url` (ingest key stays out of the public repo). Woodpecker in the Launcher. [runbooks/woodpecker.md](runbooks/woodpecker.md). **Gotchas closed:** YAML colon-space (`Content-Type: …`) → use a `|` block; Port webhook mapping must be **Saved** before the event fires (no replay). **Deferred:** real build/test/deploy pipelines for the weyland images (replace manual rsync+build), cron triggers → **B57**; Stud.IO migration onto the farm → **B57**.
- **B58** — **IaC (two lanes: Argo CD for k8s + OpenTofu for the rest)** — supersedes the manual-rsync posture ([[deployment-approach]] now: GitOps for onboarded k8s apps). **Tool calls:** **Argo CD** (GitOps) for the **k8s** lane — chosen over Flux (the dashboard wins, footprint is noise on a 32GB box); **OpenTofu** (OSS Terraform fork) for **non-k8s** — Proxmox VMs/CTs + SaaS (Port/GitHub/DNS). NOT a direct CI→CD wire — git is the seam (handoff = B57). **(a) Argo lane — DONE 2026-06-22:** `argocd.weyland.lab` (helm, `server.insecure` behind Traefik, local admin — OIDC via Keycloak with B1); **app-of-apps** root watching `k8s/argocd/applications/`; **28 apps onboarded** (20 raw auto-sync + 8 helm multi-source, chart-from-repo + values-via-`$values`). Deploy flow = **edit → push → Argo reconciles** (rsync retired). Skipped (still running, not GitOps-tracked): istio (istioctl), argocd-self, port-exporter, traefik/coredns/rbac (k3s), code-quality Jobs; headlamp deferred. [runbooks/argocd.md](runbooks/argocd.md). **Gotchas:** `ServerSideApply=true` for big CRDs (256KB annotation cap); helm `releaseName` must match the LIVE release (kube-prometheus-stack release = `monitoring`); Helm→Argo adoption shows a bigger diff — sync deliberately. **(b) OpenTofu lane — DONE 2026-06-22:** spine proven (runs from rogueone; **state in MinIO** S3 `s3.weyland.lab/tofu-state`, path-style, creds via env — `AWS_*` MinIO + `PORT_*` Port). **Port's 7 blueprints codified** (`tofu/port/`, brownfield CLI `tofu import`, clean no-op plan): cost, ci_pipeline, glitchtip_issue, feature_flag, code_quality, security_scan, endpoint. [runbooks/opentofu.md](runbooks/opentofu.md). **Gotcha (cost an hour):** port-labs provider source-type (`port-labs`) ≠ resource prefix (`port_`) → `-generate-config-out` writes `provider = port-labs` per resource → phantom `hashicorp/port-labs` poisons `init`; fix = strip those lines + CLI import (not `import` blocks). **Proxmox DONE 2026-06-22:** all **5 guests imported** (`tofu/proxmox/`, `bpg/proxmox`, API-token auth, state in MinIO) — CTs ollama/whisper/hermes (`proxmox_virtual_environment_container`) + VMs openclaw/mother (`proxmox_virtual_environment_vm`); mother's raw passthrough disk (4TB Seagate) frozen via `lifecycle ignore_changes=[disk]`. bpg gotcha: `-generate-config-out` emits write-invalid sentinels (`cpu.units=0`, `architecture/affinity/hugepages/entrypoint=""`) → omit them; `mac_addresses` computed → remove; `timeout_*` config-only. **GitHub DONE 2026-06-22:** weyland-lab repo codified (`tofu/github/`, `integrations/github`, PAT auth, CLI import). **Justified skips:** rest of Port (actions/scorecards/dashboards/entities — Port-managed defaults + integration-generated, or live *data*; NOT authored config → tofu would fight Port's lifecycle), and DNS (CoreDNS = a k8s ConfigMap, Argo's domain; no external zone). **B58 COMPLETE** — k8s (Argo, 28 apps) + non-k8s (OpenTofu: Port 7 blueprints + 5 Proxmox guests + GitHub repo) all codified; the rest of the IaC surface is either Argo's domain or not-our-config.

### Extras / Optimization
- **B57** — **Build farm: GitOps CI→CD + Stud.IO migration** — ✅ **DONE 2026-08-18 (both a + b) [Linear EMA-46].** deferred from B56. **(a) ✅ DONE 2026-08-18 — GitOps CI→CD handoff (Woodpecker↔Argo, decoupled via git — NOT a direct wire):** git-as-seam, not Woodpecker calling `argocd sync`. The weyland-lab `.woodpecker.yml` (`detect-changes → build → kubeconform → deploy-handoff`) builds the weyland-built images via a **persistent `buildkitd` Deployment** (`k8s/woodpecker/buildkitd.yaml`, Argo app `woodpecker-buildkitd`; the step is a thin `buildctl --addr tcp://buildkitd:1234` client — daemonless BuildKit couldn't do its mounts in an ephemeral step pod on k3s), pushes `git-<sha>` to `registry.weyland.lab`, and **opens a tag-bump PR** (`github_token` secret) → you merge → **Argo** reconciles → rollout. SoT `scripts/ci/images.tsv`; **stateless change detection** (diff each image's context from its deployed `git-<sha>`); nightly **01:00 NY** cron (`0 5 * * *` UTC) + manual. Validated live: `store-scaler` → `git-ec59b430`. Registry prerequisite was met by **B-RT** (`registry.weyland.lab`). **Gauntlet gotchas:** `fs.inotify.max_user_instances` must be raised on **mother** (not rogueone) 512→8192 (codified `nodes/mother/host/sysctl.d/99-weyland-buildkit.conf`); Woodpecker silently drops `privileged` without repo `--trusted-security`; kubeconform gates the manifests. Build-status → Port (`ci_pipeline`) deferred to **B63**. Docs: [runbooks/woodpecker.md] · [diagrams/flow-weyland-image-ci.md] · [demos/weyland-image-ci.md]. **(b) ✅ DONE 2026-08-17 — Migrate Stud.IO** off its local Woodpecker (+ GH Actions runners on rogueone) onto weyland's shared build farm. STUD.io's **full CI runs green end-to-end** on the farm (3 workflows: main[clone·build·npm-install·unit-pbt·e2e·scan·perf] · plugin-scanner · roadie; a throwaway `pilot` smoke test proved execution then was removed), via `woodpecker-cli pipeline create edtbl76/stud.io --branch main` (pipelines #5–#10). **Mixed fleet** on one server, routed by the built-in `backend` label: weyland jobs = `kubernetes` (pods); STUD.io jobs = `local` (4 agents on rogueone, host shell + native docker — needs the real Go/Node/pyenv/Playwright toolchain). STUD.io's own local Woodpecker + GH-Actions runners **retired**. Off-cluster bridge = **two LAN NodePorts**: `192.168.1.243:30900` gRPC (`woodpecker-grpc-lan`, agent registration) + `192.168.1.243:30980` HTTP (`woodpecker-http-lan`, `woodpecker-cli`/REST — bypasses `traefik-forward-auth`, which 302s Bearer API calls; replaced the ad-hoc `kubectl port-forward`). Getting it green fixed **3 real roadie bugs** (documented-contract `--schema-only` didn't seed → empty e2e reference tables; sonar `pytest-coverage` SIGSEGV on host pyenv → containerized into the backend test image; `lcov.info` root-owned EPERM → containerized reown step). Docs: [runbooks/woodpecker.md](runbooks/woodpecker.md), [diagrams/flow-woodpecker-studio-ci.md](diagrams/flow-woodpecker-studio-ci.md), [demos/woodpecker-studio-ci.md](demos/woodpecker-studio-ci.md). **Remaining under B57 = part (a)** (auto-build the weyland images) + re-activate the weyland-lab repo on the farm. Keep both parallel until fully proven.
- **B63** — **Woodpecker runs → Port (weyland CI reliability signal)** — ✅ **DONE 2026-08-19 [Linear EMA-52, under B57/EMA-46].** thread (c) of the Port maturity bucket; unblocked once B57 landed real build/test pipelines. **What shipped:** every Woodpecker run's terminal status POSTs (via a `notify-port` step, ingest URL in the `port_ingest_url` repo secret) to Port's **`ci_pipeline`** blueprint (id `repo-number` → build history per run), and a **`weyland_ci_reliability`** dashboard aggregates it (status pie + count counters + runs table) — the weyland reliability view Port's stock **GitHub-Actions-only** DORA boards can't give. **Proven live across both farms + both outcomes:** weyland-lab **#12** (k8s backend → success) · stud.io **#14** (local backend → failure) · stud.io **#15** (local → success). **Two hard-won gotchas (now in the runbook):** (1) a notify step with **no `depends_on`** fires a **false green** — `when: status:` evaluates the moment a step is eligible, so a step depending only on the implicit `clone` reports `success` right after `build`, before scan/e2e/perf fail; make notify the terminal stage (`depends_on: [<all steps>]`); (2) on a **multi-workflow** repo (STUD.io's main·plugin-scanner·roadie run in parallel) `$CI_PIPELINE_STATUS` is **empty** at notify time (it reflects the whole pipeline, not one workflow), and Port silently drops an empty-enum status (`ok:true`, no entity) → fix = **two status-gated steps that hardcode** success/failure. Also hardened STUD.io's `scan` gate along the way (an OpenSSL `fix_deferred` CVE-2026-14456 in the debian base → scoped `.trivyignore.backend.yaml` accept; the new `from_secret` lines tripped detect-secrets → `# pragma: allowlist secret`). Docs: [runbooks/woodpecker.md](runbooks/woodpecker.md) · [diagrams/flow-ci-reliability-signal.md](diagrams/flow-ci-reliability-signal.md) · [demos/ci-reliability-signal.md](demos/ci-reliability-signal.md). **Architecture note (B60 EI audit, still holds):** Port = delivery/DORA layer; Grafana/LGTM/Kuma = runtime/ops — keep separate; the only cross-bridge worth building is incident signals (Kuma/GlitchTip → Port) for DORA change-failure/MTTR.
- **B53** — **Sentry SaaS** (free tier) — ⚪ **LOW (2026-08-05 — largely redundant: GlitchTip already does self-hosted error tracking; the Port↔Sentry edge is moot with Port at LOW).** deferred from B51 to Extras. Would add a native Port↔Sentry integration (Ocean exporter, richer than the GlitchTip webhook) + a cloud sink. **Why deferred:** GlitchTip already covers error tracking AND GlitchTip→Port works, so the only delta is shipping app errors **off-LAN to a third-party cloud** — counter to the self-hosted/LAN-only choice that picked GlitchTip over SaaS. Optional/demo-only; revisit only if a Port-native Sentry demo is specifically wanted.
- **B54** — **OTel app instrumentation → Tempo** — ✂️ **FOLDED INTO B49 (2026-08-05)** — thread (b) of the Observability bucket. Full scope: deferred from B51 to Extras. Instrument the Python apps (tool-server, Dagster) with the OpenTelemetry SDK → Tempo for **app-level spans** (true APM; mesh/Istio spans already flow to Tempo). Adds per-request app tracing beyond the service-to-service mesh view. Deferred: meaningful effort per app; mesh tracing + GlitchTip error tracking already cover the immediate needs.
- **B110** — **MLflow AI Gateway: fix tool-schema validation + the guardrail judge** — ✂️ **CLOSED 2026-08-05 — moot/won't-do.** The premise ("tool-calling needs the Gateway") was answered by *choosing LiteLLM/Bifrost for the agentic lane* (B111) — a deliberate two-lane split (tool-calling→LiteLLM transparent; chat/eval→MLflow Gateway normalizing), with guardrails at the **agent edge** not inline. Moving tool-calling back buys nothing functional (agent-edge guardrails + Bifrost per-VK cost already cover it); it'd only be one-gateway tidiness against a working design. The one useful half (Safety/PII judge over-blocking) was already improved this session. Full detail below.
20. **B9** — **Codebase refactoring (Python / Go / Rust / …)** — ⚪ **LOW (2026-08-12 — user set back to Low; no active driver, Python services run fine. CodeScene hotspots [`loaders.py` 4.46, `build_store_load_assets` cc=56] noted but not urgent; the 2026-08-11 rebalance promotion was over-reach).** Language/perf refactoring of any service where a rewrite earns its keep (Go or Rust for hot paths, etc.) — conditional; revisit when operational pain is real or agents are heavily modifying the codebase. No driver today; the Python services run fine. See detail below.
21. **U13** — Slim sentence-transformers image / ONNX evaluation — ⚪ **LOW (2026-08-05).** deferred decision point: evaluate (a) swap to ONNX only, (b) both sentence-transformers + ONNX, or (c) stay with sentence-transformers. Depends on whether active embedding model experimentation is in progress at the time. See detail below.
22. **B22** — **Self-hosted metasearch engine (SearXNG / etc.)** — ⚪ **LOW (2026-08-05; rebranded from "SearXNG").** Stand up a self-hosted metasearch capability, tool-agnostic (SearXNG or whatever fits). No driver today — search is already covered by Tavily + Perplexity (via Bifrost). See detail below.
23. **B18** — Spotify (Hermes tool) — ⚰️ **CLOSED 2026-07-29** (Hermes retired). If Spotify control is still wanted, re-file as a **B66-operator / MCP tool** — not resurrected here. See detail below.
24. **U16** — Weaviate UI — ⚪ **LOW (2026-08-05).** evaluate whether still needed (native Weaviate UI may suffice). See detail below.
25. **B30** — Real-time docs ingestion trigger — ✂️ **CLOSED 2026-08-05 — won't-do.** Cron/manual re-ingest is adequate; docs ingestion isn't latency-critical, so near-real-time has no real driver. Historical: self-hosted GitHub Actions runner on the LAN fires Dagster `launchRun` on push (NAT-free near-real-time). Deferred; cron fine until 15-min latency bites. See detail below.
26. **B32** — NeMo Guardrails evaluation — programmable conversational guardrails (Colang DSL: topical/dialog/jailbreak rails). Deferred from B14 (heavy framework + new language; built for dialog mgmt, not I/O scanning). Evaluate for the **agent layer** (the B66 operator's dialog/topical rails — Hermes retired), not the tool-server I/O pipeline. See detail below.
27. **B38** — **Fuzzy GraphRAG: LLM concept/entity extraction** — ⚪ **LOW (2026-08-05; re-tiered from Medium — deeply deferred, low marginal value while the frontmatter graph suffices, GPU-gated).** Over the AIDLC KB (and `docs/`) — extract entities + *emergent* relationships from **prose** (beyond the declared frontmatter links) into Neo4j, à la Microsoft GraphRAG. **Deferred from B37**, which ships the deterministic frontmatter graph (`RELATED_TO`/`SURFACES_AT`/`TAGGED`). Why deferred: heavy on local CPU Ollama (517 docs × extraction passes, re-run on change), fuzzy/non-deterministic, needs an entity/relation schema + canonicalization/dedup ("DDD" = "Domain-Driven Design"), and low marginal value while the author-declared frontmatter already yields a high-precision graph for ~free. **Revisit once** B37 proves corpus value AND/OR a bigger model / GPU lands (pairs with B7 eGPU / B33).

27b. **B126** — **Trial / adopt a spec-driven framework (B86 follow-up)** — ⚪ **LOW (2026-08-11; B86 follow-up).** [B86] decided the Method is a lifecycle *superset* of OpenSpec / Spec Kit / BMAD / Kiro → **cross-pollinate artifact notations, don't migrate**. This item = actually execute a slice of that: **(a)** trial **OpenSpec** (brownfield delta model) or **Spec Kit** (constitution + `analyze` gate) on **one small unit** to feel the discipline first-hand ($0 / MIT / agent-agnostic / reversible); and/or **(b)** fold the borrowed notations into the Method — **delta specs** (ADDED/MODIFIED/REMOVED) into Iteration-N artifacts · **EARS notation** into Requirements Analysis · a checkable **constitution** rendering of the always-enforced baseline · **context-engineered unit files** (BMAD). No tool migration; **not Kiro** ($0 violation — managed AWS / Bedrock-locked / no BYOK). Eval + decision matrix: `docs/concepts/spec-driven-frameworks.md`; memory `spec-driven-frameworks-b86`. **Gate:** low-priority/opportunistic — do it when the Method's Requirements/Units stages are next being revised, not as a standalone push.

28. **B44** — **Grafana OnCall** (incident lifecycle) — 🟡 **MEDIUM (2026-08-05; ↑ Low→Medium 2026-08-08 rebalance — incident-lifecycle / observability adjacency).** Operational value is low (solo operator = no rotations; incidents already covered by Alertmanager→Telegram + Kuma + the B45 sweep) — but kept for **demo/showcase value** (a lab showpiece of the incident-lifecycle stack). Adds structured incident timeline + postmortem log on top of existing Alertmanager→Telegram alerting. Cruft: 2 always-on pods (oncall + celery) + Redis + a Postgres DB role. **Gate:** only worth it if a real multi-service incident workflow need emerges (escalation chains, on-call rotation, postmortem process). At N=1 with Telegram already covering paging, this is a "do we ever actually use it?" bet. If it hasn't been stood up by the time the data mesh + agent platform are stable, **drop it entirely**. Grafana plugin enable only — no new Grafana pod.

29. **B45** — **Operator incident-response (agent-in-the-loop)** — ✅ **DONE 2026-08-04.** The **operator** enriches firing incidents rather than just re-paging them. `incidents.py`: a 180 s loop reads `ALERTS{alertstate="firing"}` from Prometheus **off the critical alert path** (one query unifies every firing rule incl. the blackbox synthetic downs), dedups via Postgres (`operator_incidents`), and for each **new** incident runs the agent to correlate recent logs + pod status via the MCP fleet → posts a proactive Telegram digest. **Enrich-only** (proposals dropped); noise-filtered (`severity=none` + Watchdog/InfoInhibitor/LiteLLMEgressEnabled). **Hard constraint held:** never in the paging path — direct Kuma/Alertmanager→Telegram stays the pager, so if the loop dies paging is unaffected. **Earned its keep on run 1** — surfaced a **12-day postgres-backup outage** (a wedged meshed Job + `concurrencyPolicy: Forbid` silently blocking every subsequent run) buried under 8 noise alerts; hardened with `activeDeadlineSeconds`. **Brain reliability (the enabling work):** the autonomous path needs an always-up brain, so the operator moved to **local `qwen2.5:7b` primary + Haiku health-failover** on a curated FLAT toolset (gpt-oss:20b won't fit rogueone's shared 16 GB GPU; the full 91 tools *and* the two-stage routers both broke small-model selection — see [[operator-local-brain-qwen25-flat]]). Metrics `operator_incident_sweeps_total` / `operator_incidents_notified_total` / `operator_brain_selected_total`; alerts `WeylandOperatorDown` + `WeylandOperatorSweepErrors`. **DoD swept 2026-08-04** (arch entry + `flow-incident-sweep`/`flow-operator-brain` sequences + LikeC4 + runbook + demos + prometheusrule). **Brain reliability VALIDATED in production 2026-08-06** (v20, ~1.5 days post-deploy): 24h `operator_brain_selected_total` = 100% local-primary (3/3), **0 failover** (`local_down` + `local_error` both 0), operator-attributed Haiku spend **$0** — the design behaved; local carried the load, Haiku a zero-cost backstop. Reschedulable check documented in `runbooks/operator.md` § Reliability check. Closes **Linear EMA-56** with **B32** (NeMo, done via B115).

30. **B39** — **Figma ↔ code design workflow (bucket)** — 🔴 **HIGH · ▶ IN PROGRESS (2026-08-05; B114 folded in — Stud.IO is very active).** The bidirectional Figma↔code loop via the official Figma MCP (Claude Code `figma` plugin): **design → code** (Figma → UI code) + **code → design** [B114 — extract Stud.IO's UI into a Figma design system via `figma-generate-library`/`figma-generate-design` + Code Connect]. Primary target = **Stud.IO**; also the lab UI surfaces. — Original: stand up a design-to-code pipeline using the **Figma MCP** (already available in-session): pull Figma designs/components into implemented UI code (and optionally code→Figma sync). Gives the lab's UI surfaces — U16 (Weaviate UI), B3 (Backstage), future dashboards — a consistent design system instead of ad-hoc per-tool UIs. $0: Figma has a free tier. **Open:** (1) Figma account + design system/tokens; (2) which UI to target first; (3) where design artifacts live (a `design/` area in the repo?); (4) Figma-MCP auth in headless/cron vs interactive-only.

29. **B40** — **Mermaid rendering in TechDocs (B3 IDP)** — ✂️ **CLOSED 2026-08-05 — moot.** TechDocs was a Backstage feature; **Backstage retired (B59)**. Docs are now MkDocs Material (`docs.weyland.lab`), which renders mermaid natively — the whole basis of this item is gone. Historical: our `docs/` mermaid diagrams render as code blocks in the IDP's TechDocs (GitHub renders them fine, so no urgency). No official Backstage Mermaid addon exists. **Revisit approach (user-set):** (1) **try the community frontend plugin first** (`backstage-plugin-techdocs-addon-mermaid`) — interactive client-side render, but wiring it into the **new frontend system** is the risk; (2) **if that fails, fall back to build-time SVG pre-render** (`mkdocs-mermaid-to-svg` + mermaid-cli → static vector SVGs, no frontend change; optionally the official **LightBox** addon for click-to-zoom). Catalog graph + TechDocs themselves already work — this is the one parked polish item.

30. **B41** — **Self-syncing IDP (B3)** — ✅ **DONE 2026-06-19.** The IDP now tracks the repo with no manual republish. **Catalog** read live via `catalog.locations: type: url` off public GitHub (Backstage UrlReader polls ~150s; `integrations.github: [{host: github.com}]` for the unauthenticated public read; the catalog ConfigMap is **deleted** — repo is the only source of truth). **TechDocs** built+published hourly by a Dagster job (`weyland_techdocs_job` / asset `techdocs_publish`: pure-Python `mkdocs build` + `minio` upload → `techdocs` bucket; **no `@techdocs/cli`, no node**). Two mechanisms on purpose: the catalog needs no build (fetch live), TechDocs does (build+publish). Runbook `runbooks/weyland-idp.md` (retired with Backstage; the IDP is now Port). Catalog target: `github.com/edtbl76/weyland-lab/blob/main/nodes/mother/lab/weyland-platform/catalog/weyland-catalog.yaml`.

31. **B42** — **IDP Scaffolder execution (B3 slice C)** — ✂️ **CLOSED 2026-08-05 — moot.** Backstage Scaffolder feature; **Backstage retired (B59)**, Port is the IDP. If golden-path scaffolding is ever wanted again it's a **Port self-service action** (B60 phase-2, deferred), not this. Historical: the golden-path template **lists** in the IDP but **can't run**: `fetch:template` + `publish:github:pull-request` hit the GitHub **API**, and this Backstage image's **node-fetch v2 throws `ERR_STREAM_PREMATURE_CLOSE` on gzipped responses** (`Gunzip` in the stack). The catalog read works because it uses `raw.githubusercontent.com` (uncompressed); the API path doesn't. **Revisit options:** (a) force `Accept-Encoding: identity` on the github integration fetch; (b) bump/patch Node or node-fetch in the image; (c) **sidestep GitHub** — bake the skeleton into the image (a ConfigMap can't hold the nested tree) + render-to-download, no PR/PAT (also removes the token that took the catalog down tonight). Token reverted, so the catalog is back on unauthenticated read. Files live (uncommitted): `catalog/templates/k8s-service/`.

32. **B43** — **Port.io IDP migration** (replacing Backstage) — ✅ **DONE (status flipped 2026-08-05 — effectively complete since B59: Port.io IS the IDP, Backstage retired, all exporters/categories live).** Historical: **IN PROGRESS 2026-06-20.** Port.io (SaaS, EU, Free tier — `app.port.io`, org `org_KyCTEN4PVUv1D3TM`) is the zero-maintenance IDP replacement for Backstage. **Live:** K8s exporter (`weyland-cluster` — full cluster topology: namespaces/nodes/workloads/replicasets/pods + Istio Gateway/VirtualService CRDs), GitHub exporter (`github-weyland` — 6 repos, Port-side IN() filter to exclude public repo GitHub-app loophole). **Live exporters:** K8s (`weyland-cluster`), GitHub (`github-weyland`), **Uptime Kuma** (`uptime-kuma` webhook → `uptime_monitor` blueprint, **16 monitors**, `kuma.weyland.lab`; [runbooks/uptime-kuma.md](runbooks/uptime-kuma.md) — needs LAN CoreDNS + mkcert CA mount), **Linear** (roadmap status tracking — issues/teams/labels; stock integration has no project/label-name support, accepted for status-only use), **Unleash** (Feature Management — `unleash` webhook → `feature_flag` blueprint, `unleash.weyland.lab`; self-hosted OSS, meshed to STRICT Postgres, flag enable/disable events ingested; [runbooks/unleash.md](runbooks/unleash.md)), **SonarQube + Trivy + Semgrep** (Code Management — `code_quality` + `security_scan` blueprints; SonarQube server `sonarqube.weyland.lab` + on-demand Trivy/Semgrep scan Jobs; [runbooks/code-quality.md](runbooks/code-quality.md)). **Categories wired so far:** Kubernetes, Istio, GitHub, Incident Mgmt (Uptime Kuma), Project Mgmt (Linear), Feature Mgmt (Unleash), Code Quality (SonarQube/Trivy/Semgrep). **Roadmap split:** this `backlog.md` = design/ordered source of truth; Linear (`emangini` workspace, 3 projects) = task status; Claude syncs Linear via MCP **ad-hoc at end of each batch** (no auto-sync); Hermes→Linear parked (B45-era). **Also landed this batch (supporting infra):** KEDA (autoscaling/run-mode engine for the data mesh — B1), prometheus-pve-exporter (Proxmox metrics → Grafana #10347), Jaeger+Alertmanager Grafana datasources (traces+alerts in Grafana), mother VM 16→32GB / 4→8 vCPU, Kuma 16→23 monitors. **All B43 categories now wired** (Cloud Cost = B55/OpenCost, CI/CD = B56/Woodpecker, both DONE 2026-06-22). **Decom DONE (B59, 2026-06-22):** Backstage torn down after Port reached catalog parity — app + 12 `backstage_plugin_*` DBs + `weyland_idp` role + MinIO `techdocs` bucket + `weyland_techdocs_job` Dagster asset all removed. B42 moot. **B43 effectively complete — Port.io is the IDP.**

### Next — finish Port, retire Backstage (the two big steps after B58)
- **B59** — **Backstage → Port parity, then RETIRE Backstage** — **✅ DONE 2026-06-22.** Reached full catalog parity in Port *first*, then tore Backstage down. Catalog: 5 custom blueprints (`domain`/`system`/`component`/`resource`/`api`) + **26 entities** (1 domain · 3 systems · 11 components · 6 resources · 5 APIs) + dependency graph + **the upgrade Backstage couldn't do: live `component → k8s_workload` links** — built via MCP, **codified in `tofu/port/catalog.tf`** (gotcha: `port_entity` generate-out emits `provider = port-labs` + read-only `id/created_at/updated_at/updated_by` → strip both). Sidebar → a **Software Catalog** folder. Docs: a **standalone MkDocs Material site** (`docs.weyland.lab`, `k8s/docs-site/`, initContainer-builds + nginx) — browsable+searchable, **Mermaid renders (closes B40)**. Retire: Backstage app + 12 `backstage_plugin_*` DBs + `weyland_idp` role + MinIO `techdocs` bucket + `weyland_techdocs_job` Dagster asset all removed. B40 + B42 moot. **Plan as executed:** **(1) Parity audit** — enumerate what Backstage actually serves today (slices A+B: Software Catalog entities from `catalog/weyland-catalog.yaml`; **TechDocs** = the rendered `docs/` site; **Catalog Graph** = entity relations; the **API catalog** mirrored in `docs/api.md`) and confirm Port covers each — or consciously drop it. Known decision point: **TechDocs has no native Port equivalent** (options: drop it / link the GitHub-rendered docs from a Port page / keep MkDocs standalone). Catalog entities ≈ Port's K8s + GitHub exporters + blueprints; catalog graph ≈ Port relations (native). **(2) Retire** — once parity is signed off, tear down `k8s/weyland-idp/` + the `weyland_techdocs_job` Dagster asset + MinIO `techdocs` bucket + IDP Postgres role + ConfigMaps + the `idp.weyland.lab` ingress; flip arch/api/hosts/backlog Backstage → **RETIRED**. B40 + B42 (Backstage Mermaid/scaffolder) become moot. **Big step — own block.**
- **B60** — **Port maturity (bucket)** — 🟡 **MEDIUM (↓ High→Medium 2026-08-13 — deprioritized vs the active Stud.IO bridge; B112 folded in [Medium]).** Port.io is under-used (the docs-site carries much of its would-be load), but the cluster's worth one coordinated push. Threads: **(a)** self-service actions + workflows (below); **(b)** total AI-platform cost view [B112]; **(c)** Woodpecker CI signal [B63, ✅ DONE 2026-08-19]. **Phase 1 audit COMPLETE; Phase 2: scorecards DONE (→B61), self-service actions + workflows DEFERRED** (Linear EMA-49). Walked the whole sidebar (wizard dismissed; Quick Access; Engineering Intelligence; Manage Scorecards; Manage AI Assets; Builder workflows/automations). Pruned 9 redundant scorecards, the empty AI-Adoption dashboard, + a dead `ai_adoption_low_alert` Slack automation; kept the relation-wiring plumbing automations + 4 stock AI agents. Catalog tables intentionally skipped. **Architectural decision 2026-06-24 — Port = the "see" layer** (catalog/scorecards/dashboards/observability), **Hermes = the "do" layer** (acts on the lab via the tool-server): self-service actions deferred because Port's cloud **can't reach the LAN** to run infra actions (same wall as GitHub webhooks → would need a self-hosted Port execution agent), and Hermes already does ops; workflows have nothing to chain yet. **Spinoffs:** B61 (scorecards→Gold, done), B62 (AI-Dev Usage data product, done), B63 (Woodpecker reliability, ✅ DONE 2026-08-19). **Remaining (minor):** deep-audit Plan-my-day/Manage-incidents (stock), optional operator-cockpit dashboard.
- **B61** — **All `service` entities → Gold on Production Readiness** — **✅ DONE 2026-06-24** (core work; some repo artifacts a `git push` away; Linear EMA-50). **Customized the `production_readiness` scorecard for a PUBLIC solo lab:** dropped the `github_private_visibility` Silver rule (no public repo can ever pass it) so Gold is reachable; kept the rest of the ladder (Bronze README/.gitignore/url/language/team · Silver active-30d/criticality/PR-template · Gold CODEOWNERS/active-7d). **Pruned 9 redundant stock scorecards** (org/group/team-DORA duplicates — noise at N=1); kept the 6 service-level + Availability + Sonar. **weyland-lab artifacts created** (root `README.md` + `CODEOWNERS` + `.github/pull_request_template.md`); same 2 files staged into stud.io/emangini/midi (the active repos) — on push + GitHub resync those → **Gold**; algopedia + service-transformation left dormant (don't fake commits for a badge). **Value = defining production-ready for THIS lab, not the badge.**
- **B62** — **AI-dev usage data product → Port** — **✅ DONE 2026-06-24** (B37/aidlc-kb pattern; Linear EMA-51). Custom **`ai_session`** blueprint (project, duration, turns, input/output/**cache**/total tokens, models, tools-invoked, **`api_equiv_value_usd`** = what pay-per-use WOULD cost — you're on a subscription, so it's the *value* flex: ≈$12K across all projects, $0 actually spent). **Two-stage, mirrors B37 exactly:** (a) **producer** `nodes/mother/lab/weyland-platform/scripts/ai_session_feeder.py` on rogueone parses `~/.claude/projects/**/*.jsonl` → per-session summary JSON (**metrics only — no conversation content**) → `mc mirror` to MinIO `ai-sessions/`; (b) **Dagster asset** `ai_session_ingest` (group `ai_session`, 4h schedule + on-demand, B37 empty-read guard) reads MinIO → upserts to Port. Scope = relevant repos only (weyland-lab, stud.io, midi_real_book[+Etudes folded in], emangini-tailwind); weyland-lab/stud.io ai_sessions relate to their `service` entity. **Token gotcha:** `cache_read` is re-counted every turn → summing balloons to billions; headline **output_tokens** (real generation), keep cache as its own fields. **Dashboard:** "AI-Dev Usage" (Port). Producer cron + Dagster schedule keep it fresh. Dagster is the data-mesh-proper home (ties to B1).
### Hardware-Gated
33. **B21** — Agent media generation (image/video/TTS) — ✅ **DONE / CLOSED 2026-08-05 — delivered via B111's Bifrost media lane** (image = Runware, TTS = self-hosted Kokoro, video = Runway gen4_turbo — hosted providers + one self-host, through the gateway the agents already use; no eGPU needed). Original premise obsolete. Historical: requires eGPU hardware purchase. See detail below.
33. **B33** — Co-resident / warm-parallel model serving — ✂️ **CLOSED 2026-08-05 — counter-indicated by the VRAM findings.** rogueone's 16GB is a shared, contended card (rag-embed + on-demand llama-guard + display); `MAX_LOADED_MODELS=1` is a deliberate freeze/VRAM guardrail ([[rogueone-gpu-freeze-vram]]), so keeping a 2nd model resident is the wrong direction. Historical: raise `OLLAMA_MAX_LOADED_MODELS` (now 1, cgroup-bound) to keep a 2nd model warm alongside the main one → eliminates eviction/cold-start for latency-sensitive multi-model workflows (e.g. B14's conversational grounding guard, or guard+generator both warm). Gated on RAM/VRAM headroom (the "weyland box" decision / eGPU). See detail below.

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
**JupyterHub + Feast + Ray** DS — heavy tiers **on-demand via KEDA** (one node; **Feast + Ray now done** — Ray is a *persistent* head + native edge worker, not KEDA-on-demand). Dropped: Airflow, Airbyte,
Amundsen, ODM, Marquez, InfluxDB, Metabase.
**Next:** sequence into slices (storage → catalog/governance → query → transform → consumption); map onto the
3 data products (model-eval first — MLflow + eval store already exist). Picks may swap at implementation.

### B79 — Migrate Ollama + vLLM inference to rogueone (free weyland 32 GB → grow mother) — ✅ DONE 2026-07-12
**✅ DONE 2026-07-12.** Ollama moved to rogueone (`192.168.1.230`): upgraded rogueone's stale Ollama (couldn't pull qwen3-coder — 412), pulled the 3 consumed judge models (`mistral-small3.2:24b`, `deepseek-coder-v2:16b`, `qwen3-coder:30b`), set `OLLAMA_HOST=0.0.0.0` (systemd drop-in) for LAN reach, cleaned ~140 GB of junk models. Repointed consumers `.244`→`.230` (CoreDNS `ollama.weyland.lab`, weyland-tool-server, open-webui, Dagster eval defaults in eval_scores/eval_testset/model_catalog + tool-server main.py). Hermes was the only LIVE consumer (accepted it barfs). Stopped CT-102 → freed 32 GB → `qm set 101 -memory 65536` (mother **52→64 GB**, conservative; host has room to go higher later). Result: node memory **97%→79%, ~58 GB free** — the tight-node/OOM wall that dogged all of B1 is GONE. vLLM untouched (already rogueone's GPU-inference/training node; the 6 Ollama models are Ollama's role, not vLLM's).
**Decided 2026-07-10** (tentative sequencing: do it right after B1 completes; if the B1 tail gets stuck on the
tight node, pull forward). Move LLM inference off the weyland MS-A2 (CT-102 Ollama, 32 GB, CPU-bound on the weak
iGPU) onto **rogueone** (RTX 5000 Ada 16 GB, 128 GB RAM — already the vLLM/GPU-inference + Ray-training node). Two
wins: **(1)** real GPU inference (much faster + bigger models) vs the MS-A2 iGPU; **(2)** reclaim the **full 32 GB**
on the weyland host → **grow mother 52 → ~72 GB**, permanently ending the tight-node/OOM constraint that dogged the
whole B1 build (Ranger OOM, couldn't grow mother, the mem-limit remediation pass).
**Tier trade-off (accepted):** rogueone is a laptop that sleeps / rarely travels → inference becomes **best-effort**
(available when the workstation is up). Fine — solo lab, **no autonomous 24/7 LLM need** (nothing runs while
asleep). If it ever bites, add a tiny always-on fallback model on weyland later; don't pre-pay it.
**Plan:** (a) Ollama on rogueone (CUDA — vLLM + Docker Desktop toolchain already present); (b) repoint consumers —
LiteLLM gateway, OpenWebUI, Hermes, tool-server/RAG — at rogueone via the LAN NodePort / iptables-pin pattern
already used for the Ray worker + MLflow (`192.168.1.230`); (c) make LiteLLM/consumers **time out gracefully** when
rogueone is unreachable (clear error, not a hang); (d) retire the weyland Ollama **CT-102** → reclaim 32 GB; (e)
`qm set 101 -memory` mother into the freed RAM (~72 GB). Relates to **B33** (co-resident serving, hardware-gated)
and **B-RT** (remote training). See [[remote-training-rogueone]], [[hardware-topology]].

### B2 — Hermes (agent platform) — ✅ built · ⚰️ RETIRED 2026-07-23
**RETIRED 2026-07-23 — CT-104 destroyed (`pct destroy 104`).** Hermes (NousResearch agent) is decommissioned; its operator role is replaced by the **B66 operator** (fresh LangGraph pod on mother, `gpt-oss:20b` brain, Telegram long-poll, tool-server `/mcp-act`). Design rationale kept in `docs/concepts/agent-platform-design.md`; the brain decision is the B66 bake-off (`docs/demos/brain-bakeoff.md`). Below = historical.
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
  `runbooks/weyland-idp.md` (retired with Backstage; the IDP is now Port — see the B59 entry).
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
`shadow→flag/block` → **B35** (✅ done); (2) the enforcing act policy gate (allowlist/rate-limit/`block`) →
**B17+B19** (needs the gateway-asserted `actor` — see the B19 handoff); (3) PII bake → **B34**; (4) gateway auth that injects the `actor` identity → **B17+B19** (handoff
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

### B15 — Local-model coding agents (opencode / Cline / Pi / Codex) — ✅ DONE 2026-07-27 (3 harnesses proven in-hand + provider matrix)
Terminal/editor AI coding agents at `$0` — like Open WebUI (B13) but for coding. **opencode / Cline / Pi all proven
in-hand (user-confirmed)** across several free drivers (each writes `reverse.py`+`test_reverse.py`, pytest green);
**Codex** installed as the native ChatGPT-sub agent. Runbook [runbooks/coding-agents.md](runbooks/coding-agents.md)
(full recipes + provider matrix). **Best driver = ChatGPT-sub GPT-5.5 via Cline/Codex** ("Sign in with ChatGPT" — the
sub's *included* usage, not the metered API; OpenAI built this for coding agents, unlike the Claude Pro/Max ToS gray
area which stays Claude-Code-only per B26/B29). **Best keyed-free = Mistral (~60 RPM) / OpenRouter** (both confirmed
live); **Gemini 2.5 Flash** works but its 20 RPM 429s inside an agent loop (one-shot only); **Groq punted 2026-07** (the
no-card 30-RPM winner, but its signup was erroring — revisit later); OpenAI raw API key = dead (`insufficient_quota`).
Full findings there; the load-bearing ones:
- **Local models are NOT viable agentic drivers on rogueone's 16GB** (tested exhaustively): `qwen3-coder:30b` leaks
  tool-calls as `<function=…>` text; `qwen3:30b-a3b` can't disable thinking via `/v1` + leaks tool JSON; `gpt-oss:20b`
  hallucinates tool names + context-collapses (fails **identically direct and via gateway** → the model, not the
  gateway); `deepseek-coder-v2:16b` has **no tool support**. Systemic wall: 24–30B spill ~40% to CPU + load at
  `CONTEXT 4096` (Ollama default, unsettable via `/v1`) + per-model Ollama tool-template quirks. `devstral-small-2:24b`
  is the one local model worth pulling later (purpose-built for agent scaffolds), but tight 15GB/16GB fit.
- **The MLflow AI Gateway (B100 P4) is NOT usable for agentic coding** — hosted-provider *multi-turn* tool loops crash
  it (turn-2 `json.loads("")` inside MLflow); guardrails block streaming anyway. So agents point **directly** at the
  provider (Gemini) or raw Ollama. The gateway keeps its single-shot/serving role. **The eval guard-exemption
  scaffolding in `register_gateway_endpoints.py` was reverted** — re-run the script (no env override) to re-guard the
  endpoints that were detached during the eval.
- **3 harnesses proven in-hand** (opencode v1.18 / Cline v3.0.46 / Pi v0.73) + **Codex v0.145 installed** — clean tool
  protocols, real multi-step tool-use, `$0`; the model/provider was always the variable, never the harness. Per-harness
  setup + gotchas in the runbook (opencode: `limit` block for picker visibility + stale-server 400; Cline: ChatGPT
  sign-in **or** `openai-compatible` provider with placeholder key + per-run `-k` from env; Pi: built-in `google` +
  custom `models.json` where **`compat.supportsDeveloperRole:false`+`supportsReasoningEffort:false` is mandatory** or
  Mistral/OpenRouter 422; Codex: `codex login` → Sign in with ChatGPT). Multi-provider configs are live on rogueone
  (`~/.config/opencode/opencode.json`, `~/.pi/agent/models.json`).
- **Optional follow-up (not blocking):** revisit **Groq** signup when it stops erroring (best no-card portable driver);
  `OLLAMA_CONTEXT_LENGTH` bump + `devstral-small-2:24b` if local is ever revisited.

### B104 — AI dev-tooling landscape evaluation ("tech nerd" survey) — 🟡 MEDIUM (↑ Low→Medium 2026-08-11 rebalance)
A survey/evaluate item: assess the current AI-augmented dev-tooling landscape against the lab's needs + the **$0
constraint** (free-tier / OSS / self-hostable = build candidate; enterprise-SaaS-only = desk-note & park). Extends
**B15** (coding agents). ✅ = already in the lab. Grouped by category:

- **AI coding assistants / IDEs** — GitHub Copilot · Cursor · Windsurf · **Codex** (✅ B15). $0 lens: Copilot free tier
  + Codex-via-ChatGPT-sub are viable; Cursor/Windsurf are paid *editors* (free tiers exist) — evaluate vs the B15 CLI
  agents (which we already proved) rather than as replacements.
- **AI code review** — CodeRabbit · Qodo (ex-Codium). Both have free/OSS-friendly tiers; complements the SonarQube +
  scan-suite lane (B47/B90).
- **Security — SAST / SCA / cloud** — Snyk · Veracode · Checkmarx · **Semgrep** (✅ B47) · Wiz. Semgrep OSS already runs;
  Snyk has a free tier; **Veracode / Checkmarx / Wiz are enterprise SaaS ($0-hostile) → comparison-only, no build**.
- **AI test generation / automation** — Diffblue (Java unit-test gen) · Qodo (tests) · Playwright · Katalon · Mabl ·
  TestRigor. Playwright is OSS + viable; the rest are paid (free tiers vary). **Gated on a real app UI to test** (≈none
  yet — lands with stud.io / B46).
- **Load / performance testing** — k6 · JMeter · Gatling. All **OSS + self-hostable** — the realistic build here: a
  perf baseline against the tool-server / AI gateway / Trino.
- **API** — Postman AI. Free tier; complements the existing `api.md` / OpenAPI surface.
- **Docs / knowledge (AI)** — Mintlify · GitBook AI · NotebookLM · Mermaid AI · Otter.ai. NotebookLM + Mermaid are free;
  Mintlify/GitBook are paid docs SaaS (vs the existing MkDocs `docs.weyland.lab`); Otter.ai = transcription (niche solo-lab).

**Approach:** most are SaaS with free tiers of varying usefulness on a $0 LAN lab, so the eval is largely "which earn a
slot vs which get desk-noted." Realistic build candidates = the OSS ones (Semgrep✅, Playwright, k6/JMeter/Gatling,
Mermaid, NotebookLM); the enterprise scanners (Veracode/Checkmarx/Wiz) and paid IDEs are comparison-only. Sequence after
the current agent/RAG threads; pick the 2–3 highest-value OSS ones to actually stand up.

### B105 — Dagster job observability / progress logging — ✅ **DONE 2026-08-07.** All four sub-items hold: progress logging in long loops + batched encode (B74/v12) + phase/embedding markers (`aidlc_kb`, `_build_vectors`, cockroach per-table, Cassandra per-200k-rows via B121 — all verified firing live on the 2026-08-07 hydrate runs) + **structured op/asset metadata in the run UI** (51 assets emit `MetadataValue` — rows/chunk counts/etc.). The silent-step trap (running-vs-wedged indistinguishable) is closed across the ingest + datasets-hydrate jobs. _(Was 🔴 HIGH; ↑ Medium→High in the rebalance — real incident-driven ops value.)_
The ingest / re-embed jobs go **opaque during long steps** — surfaced sharply in B74: `aidlc_kb_ingest`'s embed loop ran
**silent for ~15 min** (encodes ~3,000 chunks **one at a time**; the only log lines are `read N docs` at the start and
`N/M docs → K chunks` emitted *after* the whole loop). You can't tell running-vs-wedged without dropping to
`kubectl top pod`. Make the jobs legible:
- **Progress logging in long loops** — every N chunks/docs, `log.info("embedded 1500/3000 chunks")` in the embed loops
  (`embeddings.py`, `aidlc_kb.py`) + running per-backend write counts.
- **Batch the encode** — ✅ **SHIPPED (B74, v12)**: `sentence_transformer.encode([...batch...])` instead of per-chunk: ~15 min → ~1 min **and** a
  natural per-batch progress point. (A real perf win, found during B74.)
- **Phase markers / heartbeat** — log entry+exit of each phase (read → gate → chunk → embed → write-per-backend) so a
  stall localizes to a phase instead of a silent block.
- Surface Dagster **asset/op metadata** (rows, chunk count, duration) in the run UI, not just free-text logs.
Applies across the ingest jobs (`weyland_ingestion_job`, `weyland_aidlc_kb_job`, the datasets hydrate jobs). Cheap,
high quality-of-life; the encode-batching doubles as a genuine performance fix.

### B106 — Adopt the code-review stack — ✅ **DONE 2026-08-08.** 7-tool $0 stack adopted, wired, and **validated end-to-end on PR #6** — DeepSource / CodeRabbit / Sourcery / Greptile / **PR-Agent** all reviewed it (PR-Agent via the **LiteLLM gateway** caught the planted zero-division + O(n²) smells) + **CodeScene MCP** (verify 5/5) + **ProxyAI** in-IDE; **Qodo cancelled**, CodeRabbit downgraded to free. Shipped: repo configs (`.deepsource.toml`/`.sourcery.yaml`/`.coderabbit.yaml`/`.pr_agent.toml`/`.continue/config.yaml`) + `scripts/pr-agent-review.sh` (gateway CLI; image `codiumai/pr-agent`, `custom_model_max_tokens` required) + `.mcp.json` (CodeScene MCP, env-referenced token) + `runbooks/code-review-stack.md` + **7 Port `component` entities** + the `ai-code-review` category in `quality-tools.yaml` + **DoD Pillar 7 gained the review-lane gate**. Pillar-7 scan: 0 new critical/high. Evaluated the field well beyond the 3 named (surfaced PR-Agent/Qodo-OSS, Greptile, Continue, Sourcery, CodeScene, Copilot, Claude-managed, Codacy…). Filters: **$0-forever** (not trial), **LAN can't take GitHub webhooks** (so vendor-hosted App on the public repo OR self-hostable), and **overlap** — the lab already has a full SAST lane (SonarQube + 19-tool scan-suite), so redundant SAST-AI loses to **LLM contextual review**. Owner chose **breadth over dedup**. **Decision — adopt a 7-tool $0 stack across BOTH IDE + CI/PR:** DeepSource (AI SAST; IDE IDEA/PyCharm + CI + Autofix PRs), CodeScene (behavioral/hotspots; IDE + CI), Sourcery (Python review; PyCharm + CI), **Continue** (JetBrains LLM assistant, BYO-LLM → **LiteLLM/Bifrost** — replaces paid Qodo Gen at $0), PR-Agent (self-hosted LLM PR review → gateway; Action/CLI), Greptile (codebase-aware LLM review; **PR-native** — activates once a PR flow exists), **+ CodeRabbit kept on the FREE tier** (nice format, $$ objection gone). **Cancel paid Qodo; downgrade CodeRabbit paid→free.** Wiring split: **IDE-side** = plugin installs (Sourcery + ProxyAI; CodeScene via MCP; DeepSource SaaS-only — no usable IntelliJ plugin); **CI/repo-side → B118** (DeepSource App + Autofix, CodeScene CI, PR-Agent, Greptile). **ALL DONE 2026-08-08** — configs, installs, runbook, 7 Port entities, DoD gate, and the Pillar-7 sweep (0 new high); validated on PR #6. IDE reality vs the plan: Continue's JetBrains plugin is deprecated (Cursor acquisition) → **ProxyAI** replaced it; DeepSource/CodeScene JetBrains plugins are unavailable/2026.2-broken → SaaS + CodeScene-MCP instead.
Head-to-head of AI-augmented PR/code-review tools against the lab's needs + the **$0 constraint** (free tier for
OSS/personal). Extends **B104** (AI code review) + complements the SonarQube/scan-suite lane (**B47/B90**). Candidates:
- **CodeRabbit** — AI PR reviews (line-by-line + summaries); free for public repos.
- **Qodo** (ex-Codium) — PR review + AI test generation; free tier.
- **DeepSource** — static analysis + AI autofix; free for OSS/personal.
Evaluate on: **review-signal quality** (real issues vs noise — the [[code-quality-scan-triage]] problem), $0 viability,
and GitHub integration. **LAN gotcha:** the lab can't receive GitHub push webhooks ([[lan-no-github-webhooks]]), so any
PR-triggered review must run via the vendor's own hosted GitHub App (against the public `weyland-lab` repo), not a
lab-side webhook. Weigh overlap with the existing SonarQube/Trivy/Semgrep suite; pick **0-1** to actually adopt.

### B107 — Integrate Prefect (Horizon) as the MCP gateway — ▶ MERGED into B17+B19 (2026-07-29)
Not a standalone item — merged into the MCP-gateway half of **B17+B19** (see **B19**). NOTE: Horizon itself was
**REJECTED** on scoping (managed SaaS/cloud — clashes with LAN-only/$0-self-hosted). B19's picks are **FastMCP**
(self-hosted server-edge gateway) + **Bifrost** (client-edge MCP-tool aggregation). Linear EMA-100 merged into EMA-13.

### B108 — Generalize the demo-mode toggle across shadow systems — 🟡 MEDIUM (↑ Low→Medium 2026-08-11 rebalance)
B34 shipped a **live demo toggle for the guardrails** — `POST /admin/mode` on weyland-guard flips validators
shadow↔flag/block in-process (no restart, Argo-safe, Bearer-gated). This generalizes the ask: a **consistent way to
temporarily un-shadow / activate any observability-mode system for a demo, then revert**. The guard is the one thing
today with a real "mode" concept; the other shadow-ish systems (Dagster eval jobs, OpenLineage, DataHub ingest, the
MLflow tracing/eval lanes) don't share the primitive, so this needs a small **design pass**: what "demo mode" means per
system, whether a shared control surface (a tiny control API, or a labeled toggle in Port) is worth it vs per-system
switches, and the auth/revert-safety pattern (the guard's in-process + fail-closed + auto-revert-on-restart is the
template). **Scope at start:** inventory which systems have a shadow/advisory mode worth toggling; don't build a
framework before there are ≥2 real consumers. **Effort:** small-medium (design + per-system wiring). Follows **B34**.

### B127 — Migrate rogueone off Docker Desktop → native Docker Engine (+ STUD.io data-plane consolidation) — 🟡 MEDIUM (2026-08-12; expanded 2026-08-14)
**⚠️ SCOPE EXPANDED + PROGRESS (2026-08-14). Full plan: `aidlc-docs/b127-desktop-to-native-migration.md`; memory `b127-docker-native-migration`.** B127 grew from "uninstall Desktop" into **retire Desktop + consolidate STUD.io's shared infra onto weyland** (SonarQube + MinIO central; masterdb stays local but backed up). **ADDITIVE WORK DONE — no STUD.io downtime:** (a) MinIO S3 LAN NodePort **:30990** + scoped `studio-svc` user + buckets `studio-{photos,downloads,backups}`; (b) **nightly masterdb backup** (`studio-masterdb-backup.timer` → `wl/studio-backups`, 180-day ILM) — **production is now off the laptop**; (c) Sonar API NodePort **:30969** + `controlroom` project + analysis token; (d) genre-trainer repointed to native. **REMAINING = the STUD.io-quiet-window cutover:** app `compose`→native (adopts the pre-loaded + verified `studio_studio_db_data`), sonar/minio/agent-`.env` repoints, drop `studio_minio`+`sonarqube` from compose, uninstall Desktop → **reclaim ~574 GB** (its qcow VM disk). Backup floor: `~/Documents/Studio/backups/b127-20260813/` (checksummed).
**Root cause of the freezes — CORRECTED (2026-08-13):** the earlier "SYSTEM-RAM OOM via Docker Desktop qemu shmem leak" theory was **FALSIFIED** (Desktop wasn't running, earlyoom never fired, mem never < ~75%). The real cause is a **kernel `proc_fill_cache` NULL-deref Oops** on kernel `6.17.0-35` triggered by root `/proc`-scanners (newrelic-infra/nordvpnd) — Docker Desktop does **not** cause the freezes (memory `rogueone-gpu-freeze-vram`). B127 still proceeds: Desktop is redundant, a **574 GB** disk sink, and blocks the data-plane consolidation — just not because it fixes freezes.
**Why native is the fix (and already the workhorse):** native Docker Engine is **already installed + configured** on rogueone (nvidia runtime in `/etc/docker/daemon.json`, `/var/run/docker.sock`) and runs **all** GPU workloads (vllm / sglang / llama-guard-8b). `scripts/gpu-docker` exists *solely* to route ad-hoc commands **around** Docker Desktop to that native socket — i.e. the tool is evidence Desktop is the wrong engine here. Desktop's VM has no GPU + a separate namespace (can't run the GPU containers at all); k8s is k3s on mother (not Desktop's); CLI/compose/buildx are available native; $0 solo lab = no Desktop license/support value. Desktop is **redundant + the memory sink**.
**Scope:** (1) confirm native `docker-ce-cli` + compose + buildx plugins are present (not Desktop shims); (2) make the native socket the **default context**; (3) **uninstall Docker Desktop**; (4) verify every compose stack + GPU container runs on native; (5) **retire/simplify `scripts/gpu-docker`** (native becomes default → the `DOCKER_HOST` wrapper is redundant); (6) update docs referencing Docker Desktop / gpu-docker (arch/hosts/runbooks). **Caveat:** after uninstall, confirm the `docker` binary is native `docker-ce-cli`, not a leftover Desktop shim, so commands default to `/var/run/docker.sock`.
**Companion mitigation (defense-in-depth, do regardless):** install **`earlyoom`** (apt) — SIGKILLs the biggest `oom_score` when free RAM drops below a threshold, *before* the box wedges; covers the gap where `systemd-oomd` (swap-triggered) is blind on a huge-RAM/near-zero-swap box (it was active during the freeze and never fired). **Stopgap until then:** shut Docker Desktop off before idle/overnight + Chrome hygiene. Relates B79 (Ollama→mother), the rogueone GPU serving stack (B111).

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
**MERGED with B19 — see the Mesh item. ✅ CLOSED 2026-08-02 — the "Realm of Agents" is live; DoD landed: Console (`realm.weyland.lab/`) + A2A Inspector (`inspector.weyland.lab`) UIs · `realm-llm` Bifrost VK spend attribution (LiteLLM-native VK skipped, needs a DB) · `role-<key>` prompt-reg in Bifrost.** **Post-ship delegation hardening 2026-08-03 (v18–v20):** the Console surfaced shallow/misrouted delegation → fixed the **multi-level bug** (a delegated lead ran solo and couldn't fan out; now runs as a lead → Operator→Odin→Brokkr), made lead delegation a reliable **mandate + roster** (Haiku was under-delegating), and gave the **Operator a domain→realm routing map** (eng→Valhalla/Odin, etc.) so tasks land on the right realm. Proven: an eng task now fires Odin's full team with real tools.

**Built as the Realm of Agents** (design of record: `aidlc-docs/a2a-agent-roster.md`; concept
`docs/concepts/realm-of-agents.md`; demo `docs/demos/realm-of-agents.md`): 24 small, corpus-backed specialists in
5 Norse-named groups (Valhalla eng · Vanaheim knowledge · Midgard data · the Well research/eval/safety · Root =
Operator+Gná), one multiplexed `realm-of-agents` pod, realm-partitioned inside. **A2A on two axes:** LangGraph *inside*
a realm (a lead delegates to members-as-tools — real 2-hop) + the A2A Protocol (Agent Cards + `/route` ·
`/agents/{key}/message`) *between* realms and up from the **operator** (`delegate_to_realm` — the cross-service hop,
proven: "audit the grafana dashboards" → Gná → Verðandi → answer through Telegram). Runs on Claude Haiku
(`REALM_MODEL` override), tools via the Bifrost VK, every hop MLflow-traced, resilient (failed member → note, not a
crash). Proven: Valhalla shipped a full semver package, Midgard returned real Trino catalogs, the Well did cited web
research. **Remaining for DoD (B17 stays OPEN until all three land):** (1) the **Realm Console UI** (`a2a-agent-roster.md` §9 —
served by the pod at `realm.weyland.lab`, directory + live prompt bar, the answering god lighting up); (2) a dedicated
**LiteLLM VK** for Realm spend attribution; (3) register the `role-<key>` prompts into **Bifrost** (editable without a
rebuild). Original evaluation framing retained below.

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

### B18 — Spotify integration (Hermes tool) — ⚰️ CLOSED 2026-07-29 (Hermes retired)
**Closed** — the Hermes framing is dead. Spotify control as a feature is still plausibly wanted; if so it re-files as a
new **B66-operator / MCP tool** (not a Hermes tool). Original detail retained below for the use-case notes.

Wire Hermes's `spotify` tool (playback / search / playlists / library) — **wanted: user has concrete use
cases** (CAPTURE them here — they drive scope + priority). Disabled in B2 v1 (off-theme for a system-view
agent, and setup-heavy). **Needs:** a Spotify *developer app* (client ID/secret), an **OAuth** flow to
maintain, and a **Premium** account for playback control; calls go **off-LAN** to Spotify's cloud (low
sensitivity — music control, not infra data). **Investigate:** Hermes's built-in `spotify` tool vs an MCP
server vs n8n; token/refresh handling in the CT (`~/.hermes/`, not committed). **Open:** the specific use
cases (TBD from user); which surface (Hermes tool vs MCP). One-line `hermes tools` enable once configured.

### B19 — MCP gateway evaluation
**MERGED with B17 — see the Mesh item.**

**Pick (2026-07-29): FastMCP (server edge) + Bifrost (agent edge)** — two self-hosted pieces. Prefect **Horizon** (the
obvious first name, rolled in from the former standalone B107) was **REJECTED on scoping**: it's a managed **SaaS/cloud**
(servers run on `*.fastmcp.app`, mandatory internet + GitHub, no self-host option) — collides with the lab's LAN-only /
air-gapped / $0-self-hosted ethos and would force exposing the air-gapped tool-server to the internet. The two
self-hosted picks:
- **FastMCP** (Apache-2.0, `pip install fastmcp`) — the **inbound / server** MCP gateway (the self-hosted foundation
  Horizon is built on). `create_proxy("http://<tool-server>/mcp")` fronts the existing `/mcp` + `/mcp-act` mounts behind
  one endpoint (no rewrite, no off-LAN exposure); auth via **Keycloak** (OIDC/DCR → `RemoteAuthProvider`); the
  authenticated caller's token claims → forwarded as **`X-Forwarded-Consumer` → `guardrail_verdicts.actor`**, which
  **unblocks the enforcing act policy gate** (allowlist/rate-limit/`block` on the ACT hook, carved off B35). Reuses the
  B14 read+act seams.
- **Bifrost** — the **outbound / agent** edge, **MCP-tool aggregation ONLY**: agents (operator B66, coding agents B15)
  route their MCP-*tool* access through Bifrost. **NOT an LLM gateway here** — LLM routing stays with the MLflow AI
  Gateway (B100) + LiteLLM (B26). Three lanes, no overlap: server-MCP = FastMCP · LLM = MLflow/LiteLLM · client-MCP-tools
  = Bifrost.

$0 / self-hosted / LAN. **Scope at start:** FastMCP deployment (k8s pod, meshed, ingress `mcp.weyland.lab`) + Keycloak
client + the claim→actor mapping; Bifrost deployment + wiring the agents' MCP-tool access to it. A2A (the B17 half)
stays a later eval. (The eval candidates below are superseded.)

**Phase 1+2 SHIPPED + ENFORCEMENT LIVE 2026-07-29.** `weyland-mcp-gateway` live at `mcp.weyland.lab` — a thin auth
reverse-proxy (Starlette + PyJWT, `services/weyland-mcp-gateway/`, not meshed, Argo `mcp-gateway`), Keycloak Bearer JWT +
`X-Forwarded-Consumer` actor injection, **proven end-to-end** (`actor=weyland-operator` lands in `guardrail_verdicts`).
The enforcing act gate `policy.gate` (weyland-guard — identity / allowlist / rate-limit) rides the guard image and is
**flipped to `block` (`GUARDRAIL_MODE__policy__gate=block`)** — proven live: a no-actor act returns `decision:"block"`
(*"no actor…"*) while `weyland-operator` (via the gateway) passes. The operator (`weyland-operator`) now mints a Keycloak
`client_credentials` token (`OPERATOR_CLIENT_SECRET`, `act.py`) and routes acts through the gateway, falling back to the
direct path only when no secret is wired. Gotcha fixed: `fastapi-mcp` only forwards an allow-listed header set → tool-server
passes `headers=["authorization","x-forwarded-consumer"]` (v13). Per-agent Keycloak `client_credentials` clients
(`tofu/keycloak/mcp-agents.tf`). Runbook [runbooks/mcp-gateway.md](runbooks/mcp-gateway.md); design
`aidlc-docs/construction/mcp-gateway-design.md`. **✅ Anti-spoof DONE 2026-07-29** — the tool-server act endpoints are
locked to the gateway's SPIFFE identity via an Istio `AuthorizationPolicy` (`k8s/istio/authz-toolserver-act.yaml`, DENY
act-paths from `notPrincipals:[gateway SA]`); the gateway is now meshed with its own SA `weyland-mcp-gateway`. Proven: a
forged direct act (`X-Forwarded-Consumer: weyland-operator` from a non-gateway pod) → `403 RBAC`, operator via the gateway
still passes. **✅ MCP server fleet DONE 2026-07-29** — 6 **read-only** MCP servers (grafana · trino · k8s · postgres ·
neo4j · datahub) exposing lab subsystems an agent can query through one protocol; `k8s/mcp-servers/` (Argo `mcp-servers`),
each read-only-enforced at its own layer, all proven via `tools/list`. Runbook [runbooks/mcp-fleet.md](runbooks/mcp-fleet.md),
design `aidlc-docs/construction/mcp-server-fleet-design.md`. This *earns* the aggregation trigger (≥2 MCP servers).
**✅ Composition DONE 2026-07-30** — `weyland-mcp-compositor` (FastMCP `create_proxy`) aggregates the 6 servers → ~90
namespaced tools; gateway routes **`/mcp-fleet` → compositor** (`/mcp` stays → tool-server for RAG). **✅ Operator wired
to the fleet DONE 2026-07-30** — the B66 operator loads the `/mcp-fleet` tools (langchain-mcp-adapters + token-refreshing
auth + schema sanitizer), brain = **Haiku via LiteLLM** (the agentic lane — see the two-lane rule below). Demo + live
list: [demos/mcp-fleet.md](demos/mcp-fleet.md) / `scripts/list_mcp_fleet.py`.
**Two-lane rule (learned here):** agentic/tool-calling → **LiteLLM** (transparent passthrough — tools survive; governed by
spend+valve); chat/RAG/eval/judge → **MLflow AI Gateway** (its strict normalization shreds MCP tool schemas). Agent
guardrails at the edge (weyland-guard + confirm-step), not inline. **Phase 3b ✅ DONE 2026-08-01 (built as B111):**
**Bifrost** agent-edge LIVE — `bifrost.weyland.lab/mcp`, `coding-agents` VK = **232 tools**, wired into **Claude Code +
Codex + OpenCode**; plus a **Prompt Repository (241)** and **Skills Repository (583)** served as a **Claude Code / Codex
plugin marketplace** (git-served). **→ The MCP-gateway deliverable of B17+B19 is now COMPLETE / CLOSED:** Ph1-2 (auth
reverse-proxy + actor injection + enforcing `policy.gate`) · Ph3 (6-server read-only fleet + FastMCP compositor) · Ph3b
(Bifrost agent-edge + marketplace). **Residual — `B17 = A2A eval` — is a SEPARATE, deferred future item** (agent-to-agent
peer delegation, gated on the mesh growing); the *MCP-gateway* half is done. First fleet
application = **B109** (Grafana dashboard audit via grafana-mcp). Spun off: **B110** (MLflow Gateway tool-schema-validation
defect — see below). (**DNS non-issue** — `mcp.weyland.lab` resolves via the LAN DNS wildcard.)

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
  validator chain (`guardrails/config.py`), no new plumbing. **This is B17+B19 work** — the enforcing act gate
  needs the gateway-asserted `actor` above (allowlist/rate-limit are meaningless while `actor` is `NULL`). B35
  delivered only the *grounding* half of B14's original bundle; the act gate was always blocked on this identity.
  Until then, `act` is audit-only.
- **Decision recorded:** no client-supplied identity is ever trusted (anti-spoofing). Identity is a
  gateway-asserted header or absent — this work must not loosen that.

### B20 — Home Assistant integration — Maturity
**Reframed 2026-08-03 → Maturity, DECOUPLED from B66/agents.** Home Assistant is a **standalone home-automation hub** —
one pane over the consumer/physical environment (**Nest**, **Google Home/Cast**, **Alexa/Echo**, **Smart TVs**;
lights/sensors/thermostats/speakers/TVs). Its value does NOT depend on agents, so it's no longer framed as "a B66
operator tool." **Deployment DECIDED: a Proxmox HAOS VM** (bridged LAN — the devices are cloud + local-network, no USB
dongles, but local mDNS/SSDP discovery needs LAN visibility a k8s pod lacks). Specs + integration map + sequence in the
design doc: **`aidlc-docs/home-assistant.md`**. $0 except an optional one-time **$5** Nest Device Access; **no Nabu Casa**.

**The guarded agent act-tool** (operator → HA REST API via a long-lived token, through the B14/B17 guard/act confirm
rails + enforcing `policy.gate` for physical side effects) is a **separate, optional follow-on layer** — the only
agent-dependent piece, NOT part of the core. **PARKED** (design captured 2026-08-03); un-park by creating the HAOS VM →
onboarding + integrations → token → (optional) the agent act-tool.

### B21 — Agent media generation (image / video / TTS)
Enable the **operator's** `image_generate` / `video_generate` / `text_to_speech` act-tools (Hermes retired → the B66 operator / MCP gateway) — **gated on the eGPU decision**
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

### B27 — Enable Hermes Kanban skills — ⚰️ RETIRED (→ Linear)
**RETIRED 2026-07-23.** The Hermes SQLite Kanban was dropped in favor of **Linear** (roadmap lives in Linear, EMA workspace; `roadmap-sync.py` to the Hermes board was de-committed in `9d9d982`). Moot with Hermes retired. Below = historical.
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
**✅ EVALUATED 2026-08-03 → ADOPT.** Real trial (`scripts/nemo-guardrails-trial/`) confirmed NeMo's niche is
**dialog/topical control** (Colang) — a layer we hadn't built, distinct from our edge I/O scan; its input-rail is
redundant with weyland-guard and its topical-rail duplicates the operator's system-prompt scoping, but it IS the
industry standard for *conversational* guardrails. Decision: **adopt NeMo as the DIALOG layer of the guardrails platform
(B115)**, wrapping a conversational surface (Open WebUI / chat), NOT the tool-calling operator. This closes the eval; the
buildout lives in **B115**.

**NeMo Guardrails** (NVIDIA) — a *programmable* guardrails framework: rails authored in the **Colang** DSL
(topical rails = keep on-topic; dialog-flow rails = allowed conversation paths; jailbreak / fact-check rails),
wrapping the LLM as a conversational control layer. **Deferred from B14** because it's the heaviest option (a
whole framework + a new language) and built for **dialog management**, not the request/response **I/O scanning**
B14's tool-server pipeline does (Llama Guard + LLM Guard + grounding judge cover that). **Where it might fit:**
the **agent layer** (the B66 operator — Hermes retired) for dialog/topical rails — evaluate then. Not the tool-server seam.

### B34 — Evaluate + bake PII guard (Maturity / Hardening / Polish) — ✅ DONE 2026-07-29
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

**Resolved 2026-07-29 (weyland-guard `v5`→`v7`).** Triggers confirmed real: answers exported off-box + RAG over
PII-bearing mesh data. Baked presidio + `en_core_web_sm` + the `Isotonic/deberta-v3-base_finetuned_ai4privacy_v2` NER;
uncommented `llm_guard.pii` (SHADOW); pod limit `2560Mi`→`3072Mi` for the 4th model (steady 1740Mi).
- **Recall proven** — synthetic answer with name/email/phone/SSN → block, score 1.0.
- **Entity set calibrated on real answers** (`_PII_ENTITIES`): dropped `IP_ADDRESS`+`UUID` (LAN-IP / k8s-UUID noise) and
  `CRYPTO` (the NER tagged a markdown span as a crypto address, 0.99 — pure FP, no crypto use case); kept the
  regex-precise entities + `PERSON`.
- **Measured FP** (golden set, 20 answers): 3 flagged, **all false positives** (no PII in the public docs). Redact-mode
  pinned the triggers: the NER mislabels **tech nouns as PERSON** ("Traefik" → PERSON, score 1.0). Scores ~1.0 → a
  threshold can't fix it; the entity set is the lever.
- **Stays SHADOW/advisory** (like B35): pure FP on the docs corpus. `PERSON` kept for the future PII-data path; at
  promotion, context-gate it. Enforcement value is on the (b) export + (c) PII-data paths, not RAG-over-docs.
- **Also shipped: the demo toggle** — `POST /admin/mode` flips validators shadow↔flag/block live (in-process, no
  restart, Argo-safe), Bearer-gated (`GUARD_ADMIN_TOKEN`, fail-closed). Generalizing it beyond the guard → **B108**.
Files: `services/weyland-guard/{guardrails/validators/llm_guard.py, guardrails/config.py, app.py, Dockerfile}`,
`k8s/weyland-guard/deployment.yaml`. Runbook: [runbooks/guardrails.md](runbooks/guardrails.md).

### B35 — Grounding guard calibration (Maturity / Hardening / Polish) — ✅ DONE 2026-07-28
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

**Resolved 2026-07-28 (weyland-guard `v2`→`v5`).** Ran the plan; it surfaced a deeper truth than "pick a threshold."
- **Method swap — whole-answer → sentence-level.** Confirmed the whole-answer-vs-chunk NLI over-flags (shadow
  distribution: n=1050, **58% flagged at 0.5**, a huge spike at ~0). Rewrote the scorer to split the answer into
  claims, score each claim's best-supporting chunk, and average (`grounded_mean`), with markdown/citation
  normalization + newline splitting (RAG answers are markdown lists). Bounded + serialized the NLI (cap 12 claims,
  `batch_size=8`, a `threading.Lock`) after the heavier scorer OOM-killed the pod — 6 restarts, `exit 137`; limit
  `2Gi`→**`2560Mi`** + the bounds closed it.
- **Labeled split (golden set, tagged by type via `X-Forwarded-Consumer`).** Sentence-level moved the flag rate
  58%→~50% and p50 0.236→~0.57, but conceptual still flagged ~65% vs lexical ~30%. Eyeballing the actual answers
  settled it: **grounding.nli measures chunk-ATTRIBUTABILITY, not faithfulness.** Q1 (ADKAR — lists the five blocks
  verbatim from chunks) scored 0.44; Q8 ("assess a frontier provider's viability" — a good answer that *elaborates
  beyond* its chunks) scored 0.03; Q4 (silent sorting — the known B74 retrieval miss) 0.09. It discriminates
  correctly, but good conceptual answers legitimately synthesize beyond sparse chunks, so a strict gate would block
  good answers.
- **Threshold = `0.15`, stays SHADOW/advisory.** The genuinely-unattributable tail (retrieval misses + heavy
  elaboration) sits below ~0.15; `0.5` flagged attributable answers too. Set the calibrated default to **`0.15`**
  (env-overridable `GROUNDING_THRESHOLD`). **Kept in shadow** — NLI can't separate "synthesized-but-true" from
  "hallucinated," so true faithfulness gating belongs to the **LLM-judge lane (B84)**, not this guard. grounding.nli
  is a useful "answer exceeded its retrieved sources" observability signal at 0.15, not a blocking gate.
- Files: `services/weyland-guard/guardrails/validators/grounding.py`, `k8s/weyland-guard/deployment.yaml`. Runbook:
  [runbooks/guardrails.md](runbooks/guardrails.md).

### B36 — Hermes dashboard performance (Maturity / Hardening / Polish) — ⚰️ CLOSED 2026-07-29 (Hermes retired; the dashboard it optimized no longer exists)
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

### U14 — n8n: assign a purpose, then version its workflows to git (MATURITY)
- **Running-list item**: 13
- **Theme**: D — config-in-git
- **Reclassified Core → Maturity, 2026-07-21.** The audit found **zero active workflows** — the one that exists
  (`Ingest Weyland Obsidian ReadMe`) is `active: false`, its ingestion role superseded by the RAG streaming
  pipeline. Versioning an empty/retired set is not core work. "Retire n8n" was considered and **rejected** — it
  genuinely can fill gaps, it just has no wired-up job. So the real scope is upstream: **give n8n a purpose, then
  version what it runs.**
- **Candidate purposes** (all $0/LAN, each plays to n8n's event/HTTP-glue strength):
  1. **Alert enrichment (non-agent B45)** — Alertmanager fan-out → n8n → correlate (Prometheus/Loki/Port) →
     enriched Telegram; OFF the critical path (direct Kuma→Telegram stays the pager). Best architectural fit.
  2. **Cross-tool sync hub** — GlitchTip→Linear, Linear→Port, scan-suite→Linear.
  3. **External API ingestion** — scheduled pulls of LIVE/API sources (music APIs for Stud.IO, GitHub, RSS) → mesh.
  4. **Digest/reporting hub** — weekly roll-up (scans, eval leaderboard, Dagster health) → one Telegram digest.
- **Then versioning** (original scope): export DONE (`k8s/n8n/workflows.json` + README + Argo `*.yaml` include).
  Two gaps before it's REAL: no tested **restore** path (`n8n import:workflow` — export ≠ recovery) + record the
  0-active-workflows audit result. Close when n8n has live workflows worth versioning.
- Relates to [B97] (n8n key) and [B45] (incident-response — purpose #1 partially delivers it off the agent lane).

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

### B64 — Diagram tooling: migrate docs diagrams off Mermaid — ✅ DONE 2026-07-16 (LikeC4)
**Added 2026-06-25; done 2026-07-16.** The C4/architecture diagrams are now a single **LikeC4** model (`docs/architecture/weyland.likec4`) rendered two ways: a **standalone interactive explorer** (`likec4.weyland.lab`, Keycloak-gated, `k8s/likec4/` + Argo app) + **interactive in-page embeds** (`mkdocs-likec4`, `` ```likec4-view `` fences in the C4 doc pages). One model → the whole C4 hierarchy auto-generates (landscape → node topology → mother's planes → per-sub-zone); pan/zoom/drill, theme-aware. The dense planes (mesh, ops) are **sliced into sub-zones** so no view dumps 30 nodes. Model rebuilt from the LIVE manifests (~68 components), not the stale Mermaid. **Sequence/flow diagrams stay in Mermaid** (they render fine; LikeC4 is C4-only). Runbook [runbooks/likec4.md](runbooks/likec4.md).
- **D2 was piloted and REJECTED** — static SVG renders as a white box on the dark theme, shrinks-to-fit illegible on dense diagrams, non-interactive, per-diagram styling tax. Structurizr was the runner-up; LikeC4 won on modern DX + interactive in-page embeds + auto-layout.
- **Gotchas** ([[likec4-diagramming-b64]]): mkdocs-likec4 fence puts the view-id in the BODY not the info string; the plugin only discovers `likec4.config.json` UNDER `docs/`; `$` in a label = substitution (escape/avoid); nested refs need full dotted paths; dense planes need sub-zones.
- Old Mermaid C4 pages (context/container/component-mother) converted; the per-CT component diagrams (ollama/openclaw/etc.) are superseded by the model's node topology — stale-page cleanup tracked in the docs relevance audit.

### B65 — DataHub catalog integration: the datastore set in 3 tiers (B1.3 — repurposed from the candidate list)
**Restructured 2026-06-25.** B65 is now the **datastore-integration tracker** for the B1.3 "catalog every source" work (moved under B1, in progress). Every datastore sorted into 3 tiers.

**Tier 1 — HAVE → integrate now** (already running; just catalog via DataHub connectors):
**Dagster ✅** (custom emitter) · **Grafana ✅** (recipe codified, SA token via DataHub Secret → B69) · **Iceberg/Nessie ✅** (+ Dagster→Iceberg lineage) · **MLflow ✅** (+ eval→MLflow tracking, `eval_mlflow_log` → `weyland_rag_eval`) · **Neo4j ✅** (graph schema via apoc) · **Postgres ✅** (ALL DBs, `weyland` superuser, profiling on) · **Kafka ✅** (2026-07-04 — native `kafka` source → **Redpanda** B1.5, `datasets.*` event topics + registered Avro schemas; `kafka.recipe.yaml`, 02:15 daily) · **S3/MinIO ✅** (B72 custom-emit) · **Qdrant ✅** · **Weaviate ✅** (custom emit via `datahub_emit.py` emit_qdrant/emit_weaviate, lineage ← `*_write`; native connectors give no pipeline lineage / none for Weaviate) · **OpenSearch ✅** (own playground — populated with the BM25 lexical index `weyland_chunks` (775), custom emit `emit_opensearch`; hybrid *use* → [B74]; DataGrip can't talk to OS 3.7 → dim-6 = Dashboards Dev Tools) · **lakeFS ✅** (write-through dataset versioning on `music` repo, custom emit `emit_lakefs` lineage ← `datasets_commit`). _(CSV moved out → [B68].)_ Recipes + emitters in `k8s/data-mesh/datahub-ingestion/` + `datahub_emit.py`. **ALL 12 done (Kafka closed 2026-07-04 via Redpanda + native kafka source).**
_(Low-catalog-value / optional: Valkey-Redis cache; Prometheus/Loki/Tempo — observability stores surfaced via Grafana, not typical catalog targets.)_

**REUSABLE PATTERN for gated/SSO Tier-1 sources (from Grafana, 2026-06-26):** every browser UI is forward-auth gated, so a DataHub UI pull connector must (a) point at the **in-cluster service URL** (`http://<svc>.<ns>.svc.cluster.local:<port>`), NOT the `*.weyland.lab` ingress (that bounces the API call to Keycloak → 401), and (b) authenticate with a **service-specific token**. Where SSO-mapped roles can't mint that token in the UI (e.g. a non-admin Grafana role hides Service Accounts), **mint it via the service's admin API using its admin secret** — Grafana: `kubectl get secret grafana-admin` (keys `admin-user`/`admin-password`) → `POST /api/serviceaccounts` (role Admin) → `POST /api/serviceaccounts/{id}/tokens` from an in-cluster curl pod. The DataHub executor is meshed/PERMISSIVE so it reaches in-cluster services; for STRICT-mTLS targets (Postgres) the meshed executor still connects. Expect this for MLflow / Nessie / lakeFS / etc.

**Tier 2 — IMPLEMENT → integrate now** (committed in the B1 design; stand up, then catalog):
**Trino ✅** (1st Tier-2 done, 2026-06-27 — single-node, native-Nessie catalog + postgres; in DataHub w/ sibling/upstream lineage to iceberg; full gate closed; [runbooks/trino.md](runbooks/trino.md)) · **DuckDB ✅** (2nd Tier-2 done, 2026-06-27 — served via **GizmoSQL** Arrow Flight SQL (DuckDB JDBC is embedded-only → no host:port); in-memory DuckDB w/ views over the lakeFS Parquet; IDEA via Arrow Flight SQL JDBC + `emit_duckdb` catalog (platform `duckdb`, lineage ← parquet); **meshed plaintext + Istio mTLS** (resolved the TLS_SKIP_VERIFY finding); gate closed incl. `GizmosqlDown` rule + runbook; **gRPC-TLS ingress for external IDEA = B69**; [runbooks/gizmosql.md](runbooks/gizmosql.md)) · **Superset ✅** (3rd Tier-2 done, 2026-06-28 — Helm 0.17.2/Superset 6.1.0; Keycloak OIDC; shared Valkey cache; Trino + 11 Postgres DBs connected; 48 datasets + 15 charts + "Weyland Platform Overview" dashboard; in DataHub via native superset source; `SupersetDown`+`SupersetWorkerDown` PrometheusRules; [runbooks/superset.md](runbooks/superset.md). Gotchas: psycopg2 bootstrap install via system pip `--target` into venv site-packages; data-mesh ns needs `istio-injection=enabled` label for STRICT mTLS Postgres; mkcert CA bundle for Keycloak back-channel; `SUPERSET_SECRET_KEY` in `extraSecretEnv`; Argo `terminate-op` pattern for stuck syncs.) · **TimescaleDB ✅** (4th Tier-2 done, 2026-06-28 — `timescale/timescaledb-ha:pg16`, ns `data-mesh`; 5 hypertables (eval_scores_ts, guardrail_verdicts_ts, dagster_run_durations, unleash_feature_metrics, datahub_ingestion_runs); hourly Dagster feed (`weyland_timeseries_job`); DataHub `emit_timescaledb`; Superset 10 charts; Grafana datasource; `TimescaleDBDown` PrometheusRule; [runbooks/timescaledb.md](runbooks/timescaledb.md). Gotchas: DataHub GraphQL `lastExecRequest` → `executions.executionRequests`; GraphQL only reachable in-cluster; `max_connections=200`.) · dbt Core · Flink (B1.5) · ClickHouse · Cassandra · CockroachDB · MySQL/MariaDB · MongoDB · Feast (B1.8). _(Kafka pairs here w/ Flink.)_
_(KEDA on-demand for the heavy/occasional ones per the run-mode tiers.)_

**Tier 3 — KEEPERS → re-eval AFTER Tiers 1+2, BEFORE any resource change** (the additive / zero-local-cost keeps from the candidate cull):
Doris (OLAP variety, on-demand) · Spark (big-data compute, on-demand) · RDF/triplestore (semantic-web, lightweight) · Okta · BigQuery · DynamoDB (cloud SaaS — zero local cost). Dropped candidates → [B67]. **Tier-3 re-eval folded into [B85] (data-store-mageddon v2, 2026-07-16) — verdicts: RDF ✓ graduate-when-needed; Doris ~ marginal; Spark/Okta/BigQuery/DynamoDB ✗.**

**Sequencing gate (the point of the tiers):** do Tier 1 + Tier 2 → **measure the actual always-on / on-demand RAM footprint** → THEN re-evaluate Tier 3 keepers AND size the mother vCPU/RAM resize to the *real* numbers. **No resource changes before that measurement** (proposed targets in chat: mother 44/16, ollama 32/8, OpenClaw kept 6/2 — but confirm against measured footprint).

**✅ Dagster (Tier 1) — DONE via custom emitter (2026-06-26).** 17 datasets + lineage in DataHub (15 original + the 2 iceberg_export assets).
- **Why not the standard paths (both dead on Dagster 1.13.10):** OpenLineage-dagster supports ≤1.6.9 (removed 2025). The acryl-datahub-dagster-plugin's `datahub_sensor` is built on Dagster's `run_status_sensor`, **broken since 1.7.3** ([dagster#21526](https://github.com/dagster-io/dagster/issues/21526), overwhelm + cursor-fix removed [dagster#19224](https://github.com/dagster-io/dagster/issues/19224)): daemon logs `Checking for new runs… skipped` every tick even at zero run volume → indices stay 0. Not fixable by config.
- **What works:** `weyland_pipeline/datahub_emit.py` — walks `all_assets`, emits per asset a Dataset (name + **description** + `dagster_group` custom-prop) + a **group tag** + UpstreamLineage, to GMS via the `datahub` REST SDK. Wired as `datahub_catalog_emit_job` (op) + hourly `ScheduleDefinition`. `requirements.txt`: dropped the plugin → plain `acryl-datahub`. Sensor + its imports removed from `definitions.py`. Idempotent (DataHub upserts). Baked + schedule-safe (39 MCPs: 15 props + 15 tags + 9 lineage).
- **Enrichment DONE (2026-06-26):** descriptions (14/15 assets have one — `model_catalog` doesn't) + group as prop+tag. **No column schema** — confirmed the assets carry no `TableSchema` metadata (they're non-tabular: embeddings, vector/graph writes), so there's nothing to map; the schema tab stays empty by nature, not omission.
- **Bring-up gotchas (cost the bulk of the session):** (1) GMS metadata-auth needs a DataHub PAT → `datahub-token` secret in the weyland ns. (2) **Long-JWT paste-mangling** on the secret's command line → use `read -rs` not `--from-literal='<paste>'` ([[feedback-verify-secret-after-create]]). (3) **The real blocker: `DATAHUB_GMS_TOKEN` env was `len=0`** — we added it to `user-code.yaml` but never pushed, and the dagster Argo app's **selfHeal stripped the manually-applied env back to git state**. Fix = push the manifest, never `kubectl apply` ([[feedback-remind-to-push]] / [[argocd-gitops-gotchas]]). (4) Deploy = manual `docker build` + `k3s ctr import` (`:local`/`Never`; a registry now exists — `registry.weyland.lab`, B-RT — so this could move to a pushed tag) — Argo can't deploy image contents, only manifests.

### B66 — Operator Agent Platform (consolidation — supersedes 13 fragmented agent items) — ✅ CORE DONE 2026-07-24
**✅ SHIPPED 2026-07-24 — `weyland-operator`, a LangGraph pod on mother.** Text the lab from anywhere → it acts.
Built in 4 parts: (1) **agent core** — `create_react_agent(gpt-oss:20b, tools)` over the tool-server read tools,
native tool-calling; (2) **Telegram long-poll ingress + allowlist + Postgres session memory** (`operator_sessions`,
last 10 turns); (3) **act tools + app-level confirm-step** — the LLM can only `propose_act`, the *app* fires only on
an explicit "yes" (four rails: allowlist · confirm · `act.py` fail-closed job-allowlist · tool-server `Hook.ACT`);
(4) **wrap** — SealedSecret, MLflow `operator` traces, [runbooks/operator.md](runbooks/operator.md),
[demos/operator.md](demos/operator.md), [diagrams/flow-operator.md](diagrams/flow-operator.md), design
`aidlc-docs/construction/operator-agent-design.md`. Brain = `gpt-oss:20b` (bake-off winner); Hermes/OpenClaw retired.
Fresh shell, raw-httpx Telegram, `asyncio.to_thread` for the blocking loop, per-op meshed Postgres. **Enhancements**
(Spotify/NeMo/incident-response/error-tracking = Linear EMA-56) remain the Low sibling tree. See [[weyland-guard-b70]],
[[b66-operator-brain-bakeoff]].

**Added 2026-06-25.** Folds the scattered Hermes/OpenClaw work into ONE effort: a **Claude-brained, multi-ingress operator agent**. **Thesis:** the agents' real value is *remote/mobile ingress that acts on the lab* (text it from anywhere → it acts); the failure is the **brain** — Hermes on weak free/local models is slow/unhelpful, OpenClaw "feels" better. Fix = give the agent a **Claude brain via the $0 subscription-headless path** (`claude -p` / Agent SDK with the Max-subscription auth — NOT the paid Claude API, which is exactly why the Claude-brain path was *declined* at B26). Keep the existing ingress + act (`/mcp-act`) + tool plumbing.
- **Workstreams (each absorbs an old item):**
  - **Brain** — Claude via subscription-headless ($0); revisits the B26-declined decision with the new path.
  - **Base agent** — pick **Hermes vs OpenClaw** as the gateway (**resolves B28**): Hermes = blessed/stable but slow; OpenClaw = fast/responsive but deprioritized/fragile. Decide reuse-OpenClaw-responsiveness vs Hermes-base at build time; **do NOT decommission OpenClaw until decided** (now a reuse candidate, not an auto-retire).
  - **Ingress** — Telegram (live) + other channels (Whisper voice, web).
  - **Act + incident** — act tools (`/mcp-act`, live) + **B45** (agent enriches/acts on incidents, off the critical alert path).
  - **Tools** — **B20** (Home Assistant), **B18** (Spotify), **B21** (media-gen).
  - **Guardrails** — **B32** (NeMo dialog/topical rails for the agent layer).
  - **Mesh / delegation** — **B17+B19** (A2A + MCP gateway), **B15** (local coding agents Hermes delegates to).
  - **Ops** — ~~B36 (dashboard perf), B52 (Hermes error tracking)~~ both **⚰️ CLOSED/MOOT 2026-07-29** (Hermes retired).
- **Split into two efforts (2026-06-25, mirrors Linear):** **B66 = core** (brain, base agent, ingress, act, mesh — keeps B15, B17+B19, B20, B28) · **"Operator Agent Platform (Enhancements)"** (Linear EMA-56, sibling, Low) = the agent extras **B45** (operator incident-response, reframed), **B32** (NeMo dialog rails). *(Hermes-framed items closed 2026-07-29: B18 Spotify, B36 dashboard, B52 error-tracking.)*
- **Done base (context, not re-scoped):** B2 (platform), B26 (LiteLLM brain), B27 (kanban).
- **Resource note:** OpenClaw's 8 GB/4 CPU retirement (floated in the reallocation plan) is now **contingent on the base-agent decision** — if OpenClaw is reused, it stays.
- **Sequencing (decided 2026-07-22):** B66 is the **High/Core umbrella** for the whole agent lane — B15/B17+B19/B20/B36 + the Enhancements sub-tree all nest under it (one parent, one tree). **Design DEFERRED by choice** — High-but-sequenced, not stalled. Two gates before the big-rock design starts: (1) **B70 first** (agentic RAG on LangGraph — unblocked, High, produces the framework evidence that informs the base-agent call); (2) a **brain-viability spike** — prove the $0 Claude-via-Max-subscription-headless path (`claude -p` / Agent SDK) is technically viable on CT 104 AND acceptable under Anthropic ToS (subscription auth is for interactive use — a persistent headless agent is the risk). **If the spike fails, the B66 thesis collapses, so it comes first.** ~30 min, de-risks a big rock. **Design insight for later:** the brain decision COLLAPSES the base-agent one — a Claude brain means neither Hermes nor OpenClaw's native brain matters, so B28 becomes "which ingress+act shell," not "which brain." Own brainstorm → `aidlc-docs/` when reached; orthogonal to the data mesh.
- **BOTH GATES CLEARED (2026-07-23):** (1) **B70 done** (LangGraph agentic-RAG shipped — framework evidence in). (2) **Brain-viability spike done — and it OVERTURNED the thesis.** The bake-off (`docs/demos/brain-bakeoff.md` + `scripts/brain-bakeoff/`) found **`gpt-oss:20b` (local) MATCHES Claude Haiku 3/3 on the operator loop** — tool-use over the tool-server tools (status / RAG / pipeline), incl. multi-step conditional chaining + self-correction + honest-negative — faster and $0. So we **don't need the Claude brain**. Subscription-headless *did* prove technically viable + ToS-defensible for human-triggered lab use (`claude -p` runs headless on the Max sub; the only ToS risk was autonomous/unattended use, which "everything is person-kicked-off" rules out) — but it's **moot** since local suffices. **Decision: operator brain = `gpt-oss:20b`** (local, $0, on-LAN, already the tool-server default); **Haiku (API, ~cents/mo) = documented fallback** for cloud-offload / always-up / the autonomous **B45** path. **(SUPERSEDED 2026-08-04 — see B45:** gpt-oss:20b doesn't fit rogueone's shared 16 GB GPU (RAG embedder + on-demand llama-guard-8b + display → it spills to CPU and stalls); the brain is now local **`qwen2.5:7b`** primary on a curated FLAT toolset + **Haiku health-failover** — [[operator-local-brain-qwen25-flat]].)** Note "local" is NOT uniform — gpt-oss:20b ≫ qwen3-coder:30b ≫ mistral-small (malforms args) ≫ deepseek-coder-v2 (broken tool-calling); it's gpt-oss specifically. **Act-path bake-off DONE (2026-07-23, dry-run — nothing executed):** gpt-oss:20b **8/8 = Haiku** — correct act tools + valid `job_name`s (no hallucination) + **declined all 4 safety traps** (ambiguous / destructive / unknown-job / read-not-trigger) → **CLEARED for `/mcp-act`** (qwen 6/8 but its misses erred *safe* — picked read tools, never mis-fired an act; deepseek broken). **Still design the act path with defense-in-depth regardless of brain:** the tool-server already validates `job_name` (bad job 400s, doesn't fire) + add a **confirm step** for expensive/irreversible acts. **→ Both gates clear, so B66 design can start;** with a local brain the base-agent call collapses to "which ingress+act shell" → **fresh** (reuse the Telegram ingress + `/mcp-act` plane, not a resurrected legacy agent). See [[b66-operator-brain-bakeoff]].

### B67 — Dropped datastore candidates (Extras — re-evaluate later) — SUPERSEDED by B85 (data-store-mageddon v2, 2026-07-16)
**Added 2026-06-25.** Cut from the B1.3 "ingest every source" connector pass as **redundant with the table-stakes WILL-DO set** (not for lack of merit). KEDA solves the *resource* cost of redundancy but not the maintenance / catalog-clutter / learning-overlap, so these were dropped on purpose. Parked to re-evaluate if a concrete need emerges.
- **Druid** — real-time OLAP, but the **heaviest** on the list (coordinator + overlord + broker + historical + middlemanager + ZooKeeper + deep storage + metadata DB) and pure overlap with **ClickHouse** (committed). Worst ROI.
- **Vertica** — redundant OLAP; community edition capped (1 TB / 3 nodes) + enterprise baggage.
- **Dremio** — overlaps **Trino** (federation) + **Cube** (semantic); its edge (reflections/acceleration) doesn't justify a second federation engine. **The closest "keep" call — reprieve this first if any get reconsidered.**
- **Airbyte** — overlaps **dlt + Debezium** (committed EL/CDC); heavy (server + workers + Temporal + Postgres + UI); its 300-connector catalog only matters for external-SaaS pulls (rare on a LAN lab).
- **Airflow** — pure duplicate of **Dagster** (the committed orchestrator).
- **Metabase** — overlaps **Superset + Lightdash** (committed BI); the design already said "No Metabase."
- **Re-eval trigger:** a concrete need the committed stack can't meet (real-time-OLAP gap ClickHouse/Doris don't fill → Druid/Vertica; an external-SaaS EL need → Airbyte; a Trino-acceleration gap → Dremio). KEPT instead (additive/new capability or zero-local-cost SaaS): Doris, Spark, RDF, Okta, BigQuery, DynamoDB.

### B68 — CSV / Google Sheets ingestion (DataHub) — ✂️ CLOSED 2026-08-05 — won't-do (niche polish, no driver; the mesh's real sources are already ingested)
**Added 2026-06-25.** Deferred from B65 Tier 1 to the **Maturity / Polish** tier (between Core and Extras). **BLOCKED:** find suitable spreadsheets in Google Drive first. Two paths, decided once the sheets are picked:
- **csv-enricher** — bulk-**enrich** existing entities with metadata (`tags`/`glossary_terms`/`owners`/`ownership_type`/`description`/`domain`/`subresource` for column-level/`classification`), keyed by `resource` = entity URN; arrays `|`-delimited; `write_semantics` PATCH (append) vs OVERRIDE. **Requires entities already ingested** (B65 Tier 1 sources) so there's something to enrich.
- **File/S3 source** — **catalog** the CSV rows as a *dataset*: export Sheet → CSV → MinIO → DataHub S3 source infers the schema.
- Doc: https://docs.datahub.com/docs/generated/ingestion/sources/csv-enricher

### B72 — Datasets landing zone + CSV→Parquet pipeline (music data) — ✅ DONE
Produced the lab's first real datasets: **Spotify audio features + FMA metadata**, landed and transformed into **five formats** (Parquet · Lance · Avro · Arrow · Iceberg) + raw CSV as silver/gold artifacts in MinIO + the DataHub catalog. The landing-zone + CSV→Parquet transform pipeline (Dagster) is the foundation the data-mesh (B1) and the per-format use cases (B73) build on. Tracked in Linear as EMA-62.

### B73 — Find/build uses for the datasets-lake formats (Maturity / Polish)
**Added 2026-06-26.** B72 produced the music data (Spotify audio features + FMA metadata) in **five formats** (Parquet · Lance · Avro · Arrow · Iceberg) + raw CSV — but they're currently **inert** silver/gold artifacts sitting in MinIO + the catalog. Build a **real use case per format** that exercises its specific strength, so each earns its keep and the format choices are validated *by use*, not just by the rationale in [datasets-lake.md](runbooks/datasets-lake.md):
- **Parquet** → analytics queries via **Trino / DuckDB** (Tier-2) — genre/feature aggregations over the Spotify set.
- **Lance** → **vector / similarity search** (LanceDB) — ✅ **DONE 2026-07-05.** LanceDB store built (embedded, Lance-native, on the lakeFS S3 gateway; same 9 vector sets as Qdrant/Weaviate via `_build_vectors`); in-process query + `emit_lancedb` catalog + **Lance Data Viewer** UI (`lancedb.weyland.lab`) fed by an event-triggered `mc mirror` (Dagster `lancedb_sync_sensor`). Nearest-neighbour over audio features works (gtzan genre-clusters). Runbook: datasets-hydration.md; diagram: flow-lancedb.md.
- **Avro** → **stream through Kafka** (producer → consumer) — the row/schema-evolution format in motion.
- **Arrow** → **zero-copy load** into polars/pandas for fast EDA — prove the IPC/transport story.
- **Iceberg** → **time-travel / schema-evolution / ACID** demo via Trino — the gold-table capabilities.
- **Goal:** each format demonstrated by a concrete workload, not left as a catalog entry. **Sequence after** the relevant Tier-2 engines exist (Trino/DuckDB, Kafka) — those are prerequisites for several of these.

### B74 — Retrieval precision (MATURITY) — ✅ SOLVED 2026-07-28 (bge-base 768 + topic-prefix)
**Added 2026-06-27. RESCOPED to MATURITY 2026-07-21** after B96. **✅ SOLVED 2026-07-28.**

**✅ SOLVED 2026-07-28 — the middle rung won: bge-base (768-dim) + topic-prefix = clean sweep, no trade.** Swapped
`BAAI/bge-small` (384) → `bge-base` (768) across every embedder, re-embedded the whole corpus, re-ran the golden set.
**All six cells up** (small → base): conceptual `context_relevancy` 0.514 → **0.826**, lexical 0.736 → **0.819**;
conceptual faithfulness 0.660 → 0.814, lexical 0.780 → 0.854; conceptual answer_relevancy 0.644 → 0.856, lexical 0.832
→ 0.873. **The conceptual/lexical gap CLOSED** (was 0.514 vs 0.736; now 0.826 vs 0.819) — bge-base lifted the weak half
**+0.31** *and* nudged the strong half up. So **no hybrid (Phase 3 permanently dead), no bge-large** — the cheaper rung
sufficed. Smoke: Q6 top-5 all `adkar`, Q10 `affinity-mapping#1`; **residual Q4** ("silent sorting" still pulls
`filtering-and-sorting` — the surface token beats 768-dim semantics, or the doc lacks that content) — one outlier vs an
0.826 average, not chased. **`embed_text` topic-prefix + B105 batching both shipped.** Full migration playbook (4
embedders, 768 re-dim, the scars) → [runbooks/embedding-model-swap.md](runbooks/embedding-model-swap.md).

**✅ Phase 1 DONE 2026-07-27 — diagnosis + first fix attempt (null result).** Inspected `/context/search` retrieval for
all 10 conceptual questions: **4/10 are outright RECALL failures** (the answer doc — `affinity-mapping.md`, `adkar.md` —
never retrieved in top-8), 1 ranking (rank-4), 1 right-doc-wrong-chunk, 4 good. **Root cause = template collision**: the
AIDLC-KB docs share a rigid section template (`## When to Apply` / `## Key Concepts` / `## Related Entries`); chunked
per-H2, those boilerplate headers embed near-identically across unrelated docs, so a conceptual query matches the
*section-type* across many docs instead of the *topic*. So it's a **recall** problem (reranker/BM25 can't fix a doc
that's never retrieved), NOT the ranking problem B96 hypothesized. **Fix attempted — contextual chunk headers** (prepend
`source_name — chunk_title` to the embedded text; `embed_text()` in `chunks.py`, used by `embeddings.py` +
`aidlc_kb.py`): re-embedded the KB (bge-small) and re-ran the golden set. **Result = null:** conceptual
`context_relevancy` 0.514 → **0.529 (+0.015, within judge noise)**; smoke probe recovered only 1/3 recall-failures
(ADKAR surfaced; affinity-mapping's hard queries didn't). The mechanism is real (ADKAR proves it) but **bge-small
(384-dim) lacks the resolution** to bind paraphrased conceptual queries to the right doc when competitors share surface
tokens. `embed_text` kept (harmless, recovered ADKAR). **Decision → the "middle rung": B105 batch-the-encode + swap to
bge-base (768-dim), A/B vs small on the golden set; bge-large (1024-dim) the heavier fallback.** Compute note: embedding
is **CPU-on-mother (no GPU in the path)** — RAM fine, but a full bge-base re-embed is slow until B105 batching lands
(the small re-embed took ~20 min unbatched, ~3,817 chunks). Swap is a **384→768 dimension migration**: recreate the
pgvector column + qdrant/weaviate/neo4j collections AND flip the tool-server's query embedder to match.

**The original premise is FALSE.** B74 was written as "dense embeddings are weak on exact identifiers (config keys, flags, error codes, paths, commands) that BM25 nails". Measured on the golden set, **lexical questions BEAT conceptual ones on every metric at every retrieval depth** (k=3: lexical `context_relevancy` 0.736 vs conceptual 0.514). Dense retrieval handles identifiers *well* here. Full evidence: B96 above + [runbooks/eval-harness.md](runbooks/eval-harness.md).

**What the data actually says.** The weak half is CONCEPTUAL retrieval, and it is a **ranking** problem, not a recall or volume one: conceptual `context_relevancy` moved only 0.514 → 0.563 while k nearly TRIPLED (3 → 8). Depth is a **trade** — it buys conceptual synthesis and costs lexical precision (dilution; lexical faithfulness falls monotonically 0.780 → 0.716 → 0.691), and it is roughly linear, so there is no free middle. `EVAL_ASK_LIMIT` stays at **3**.

**So this is no longer "wire up BM25".** It's *get the right chunks into a SMALL top-k*, which is a maturity/polish theme with several candidate mechanisms that should be **compared, not assumed**. Every phase is measured against the same golden 20-question exam, sliced conceptual-vs-lexical — that instrument now exists, which is what makes this tractable.

**Phase 1 — Diagnose (cheap, do first).** Conceptual `context_relevancy` is 0.514: look at what is ACTUALLY being retrieved for those 10 questions. Is it wrong-document, right-document-wrong-chunk, or split-across-chunks? Each implies a different fix, and the answer may make Phases 2-4 unnecessary. Likely suspects: chunk size/overlap vs. the conceptual docs' structure, and embedding-model fit (`bge-small-en-v1.5`, 384-dim).
- **Gate:** a written answer to "why are 5 of 8 retrieved chunks irrelevant for a conceptual question?" No code required.

**Phase 2 — Reranker (highest expected value).** A cross-encoder over an over-fetched candidate set (retrieve ~20, rerank, keep 3). This is the textbook fix for exactly this shape — precision without dilution — and it should improve BOTH halves rather than trading them. Cost: another model resident on rogueone's 16 GB GPU alongside Ollama ([[remote-training-rogueone]] — mind the desktop-freeze constraint), or CPU on the tool-server (already CPU-bound at ~2.8 cores under eval load).
- **Gate:** conceptual `context_relevancy` ≥ 0.60 with lexical NOT regressing below 0.72.

**Phase 3 — Hybrid BM25 + dense (RRF).** The original scope, now on honest grounds: fusion as a *precision* mechanism. The OpenSearch lexical index (`weyland_chunks`, kept in sync by `opensearch_write`) is already built and cataloged (B65) and remains unused at query time. Keep fusion configurable (toggle + weights/k) so dense-only stays available. **Expect modest gains** — the data says the lexical half is already the strong one, so this mostly hardens what works rather than fixing what doesn't.
- **Gate:** measurable improvement on the golden set that a reranker alone did not already deliver.

**Phase 4 — Per-query-type k / adaptive retrieval.** The trade-off is real and directional: identifier queries want a tight top-3, synthesis queries want more. Classify the query (or use the retrieval score distribution) and set k accordingly — a smarter feature than any constant, and it captures both sides of the trade the measurements exposed.
- **Gate:** beats the best fixed-k configuration on the SUM across both halves.

**Feeds B70** (agentic RAG) — whatever retriever wins here is what the LangGraph loop calls. **Do not start any phase without re-reading the B96 numbers first.**

### B69 — Platform completeness / gap remediation (post-B1) — ✅ DONE 2026-07-22
**Added 2026-06-26. ✅ DONE 2026-07-22** (tail fully cleared; last residual = B97 n8n-key untrack + the scan-suite `secret_files` guard). **Re-verified against git + live cluster 2026-07-20.** Output of the multi-agent completeness audit (`docs/completeness-audit.md`) — artifacts that "run once" but aren't operationally complete (trigger / lineage / GitOps-reproducibility / monitoring / docs). **Data-mesh-scoped gaps (14) solved inline as part of B1**; this item is the **platform-wide set (28: 9 high / 14 med / 5 low)**. Full register + per-item status: `docs/completeness-audit.md`.

**✅ Closed:** Wave 1 entirely (data-mesh alert loading · dead-man's-switch · cube plaintext key · backup coverage · `telegram-test` · Argo onboarding) · Wave 2 SealedSecrets (53 sealed) · Wave 3 images-off-`:local` · code-quality + sonar weekly CronJobs · SPOF probes + 19-endpoint blackbox synthetic monitoring · the 07-18 push list (all committed).

**Tail worked 2026-07-20:** ✅ **LGTM self-monitoring** — `k8s/monitoring/lgtm-self-monitoring.yaml`: ServiceMonitors for loki/tempo/alloy + `LokiDown`/`TempoDown`/`AlloyDown`, each pairing `up == 0` with `absent(up)` so a vanished target can't go silently blind (same pattern as `BlackboxProbesMissing`). Loki's selector needs `variant DoesNotExist` — `loki`, `loki-headless` and `loki-memberlist` carry identical app labels, so a naive selector double-counts. Tempo's metrics port is `tempo-prom-metrics`, not `http-metrics`. ✅ **`weyland-image-prune.timer` installed** (next Sun 15:09 UTC) — it had been authored on 07-18 and never enabled. ✅ **roadmap-sync codified** (`nodes/weyland/hermes/roadmap-sync.{service,timer}`, daily 06:30, Persistent).

**⏸ Hermes heartbeat — GATED ON B66, not open.** Hermes is **shut off**; the agent lane is consolidated into B66 where the base-agent call (Hermes vs OpenClaw) gets made. A heartbeat on a deliberately-stopped service pages forever, so the units are **staged in git, not installed**: `nodes/weyland/hermes/hermes-heartbeat.{service,timer}`. Design note for whoever installs them — CT 104 is a Proxmox container outside k3s, so there is no scrape path; liveness is **pushed** to an Uptime Kuma Push monitor and gated on `systemctl is-active`, because an ungated heartbeat reports healthy from a box whose service is dead.

**✅ Triggers COMPLETE 2026-07-20** — docs-site rebuild (daily 05:30 CronJob, RBAC-verified live), eval harness (Sat 03:00/05:00, STOPPED pending a green manual run post-B79), ai_session producer (rogueone user timer, replaces an uncommitted crontab), roadmap-sync (staged for B66).

**❌ Genuinely remaining:** · GitOps misc (n8n workflows→git, LiteLLM `main-stable`→digest, DataHub recipes UI→reconciled) · delete CT-102 + `hosts.md` cleanup · Prometheus/Loki retention caps · Wave 5 docs-drift.

**⚠️ Two corrections this pass.** (1) The "data-mesh alerts silently dead" item — the register's own *biggest live risk* — was resolved by one Helm value (`ruleSelectorNilUsesHelmValues: false`), NOT the prescribed 17-file relabel; 52 PrometheusRules load fine. Acting on the register literally would have been 17 pointless edits. (2) The Argo app count below has drifted **again**: it read 28→48, live is now **59**. Disk pressure is resolved (`/` 63%, `/mnt/minio` 9%).

Original highlights (high) — historical, several now closed above:
- **Secrets management** — ~25 imperative-only cluster secrets, nothing restores them → adopt SealedSecrets/External-Secrets/SOPS (or commit `*-secret.example.yaml` shapes + `runbooks/secrets.md`). **DataHub-specific: ✅ SOLVED 2026-07-03.** DataHub UI Secrets (NEO4J_PASSWORD, MINIO_*, GRAFANA_SA_TOKEN, + WEYLAND_PG/MONGO) live in GMS memory, not Postgres → wiped on every GMS restart, silently breaking every secret-backed ingestion source at once. Fixed by injecting the creds as **`acryl-datahub-actions` pod ENV** (`extraEnvs` secretKeyRef → k8s Secret `data-mesh/datahub-ingestion-secrets`, created out-of-band so it survives GMS resets) — recipe `${VAR}` refs resolve from pod env, and the `.recipe.yaml` files are source-of-record so re-adding a wiped source is paste-and-go, no secret re-entry. See [runbooks/data-mesh-secrets.md](runbooks/data-mesh-secrets.md). (The broader SealedSecrets adoption stays open.)
- **No dead-man's-switch** — Alertmanager Watchdog routed to `null`; a total alerting-pipeline failure is silent → external heartbeat.
- **Always-firing `telegram-test` alert** committed + Argo-synced (`expr: vector(1)`) → pages every 4h; delete from git.
- **Ollama / Hermes / tool-server** — no monitoring + not reproducible from git (image `:local`/Never → ErrImageNeverPull on rebuild).
- **Istio set not onboarded to Argo** (incl. STRICT mTLS PeerAuthentication — load-bearing).
- **Kuma monitors only in SQLite**, LGTM doesn't monitor itself, forward-auth is a SPOF with no probes.
- **Prometheus scrape coverage is sparse (surfaced 2026-06-27).** Most pre-B65 services have **no ServiceMonitor** — the monitoring gate was never applied *retroactively*, so only the newer components (data-mesh, Trino) are scraped + alerted. **Audit:** `count(up) by (job)` lists every live scrape target → anything absent has no ServiceMonitor. Remediation = add ServiceMonitor + a PrometheusRule (down/error alert → Alertmanager → Telegram) per gap, prioritizing the load-bearing services. The completeness gate keeps every *new* store covered going forward; this is the retroactive backfill.
- **GizmoSQL external TLS (added 2026-06-27)** — the DuckDB Flight SQL **in-cluster** hop is Istio mTLS, but the **external IDEA→NodePort hop is plaintext over the LAN** (password in the clear; the flagged in-cluster `TLS_SKIP_VERIFY` is already gone). Fix = a **gRPC-TLS ingress at `gizmosql.weyland.lab`** (Traefik terminates the real wildcard cert, forwards h2c into the mesh) → IDEA connects TLS with a valid cert, no skip-verify. Low risk on a trusted home LAN; the honest finish for the GizmoSQL gate.
- **Grafana datasource audit + dashboards** — as new data stores are added (TimescaleDB, future Tier-2 stores), audit Grafana datasources to ensure all active stores are registered and have dashboards. Current known gap: TimescaleDB added 2026-06-28, datasource registered manually but no dashboards built yet. Build Grafana dashboards for TimescaleDB hypertables (eval score trends, guardrail verdict rates, Dagster run durations, DataHub ingestion health).
- **B109** — **Grafana dashboard audit (via grafana-mcp)** — ✂️ **FOLDED INTO B49 (2026-08-05)** — thread (c) of the Observability bucket. Full scope: audit the *dashboards themselves* for hygiene, not just datasource registration (that's the item above). Walk every dashboard read-only and report: **stale** (not updated/viewed in N months), **broken panels** (queries referencing dropped datasources/metrics — e.g. after a store is decommissioned), **duplicates/near-duplicates**, **orphans** (no folder / no owner), and **coverage gaps** (active stores with no dashboard, cross-refs the datasource-audit item). First real *application* of **grafana-mcp** (B17+B19 Phase-3 fleet, read-only `--disable-write`): the operator (B66) or a scheduled agent drives the MCP `search_dashboards`/`get_dashboard` tools, emits findings (Telegram digest and/or a `code_quality`-style Port surface). $0/self-hosted; read-only so it never mutates a dashboard. Pairs with the MCP fleet buildout — a concrete "so what does an aggregated MCP mesh let an agent DO" demo. Relates the datasource-audit item above + [[b17-b19-mcp-gateway]] / [[b66-operator]].
- **B110** — **MLflow AI Gateway: fix tool-schema validation + the guardrail judge (B100 P4 defect, spun off from B17+B19)** — ✂️ **CLOSED 2026-08-05 — moot/won't-do (the agentic lane settled on LiteLLM/Bifrost per B111; moving tool-calling back onto the Gateway buys nothing functional — see the top-down entry).** Original: the Gateway's `RequestPayload` validation is **stricter than the providers themselves**: it rejects valid MCP tool schemas (missing `properties`, `type:null`, missing `type`) — `tools.N.function.parameters.properties Field required` / `Tool not found` / `Schema type is missing` — so **tool-calling agents can't use it** (settled by a direct-to-Anthropic A/B: same tools worked off-Gateway, 400'd through it). Until fixed, the **agentic lane routes through LiteLLM** (transparent passthrough; see the two-lane rule in B17+B19 + arch §8a) and only **chat/RAG/eval/judge** traffic uses the Gateway. **Fix scope:** (a) make the tool-schema validation permissive/normalizing (accept what the provider accepts); (b) the **Safety/PII judge** (qwen2.5:7b) was *also* mis-blocking — it returned prose instead of the `yes`/`no` enum and the Gateway blocked *safe* content → **already improved** this session (rewrote the judge prompts strict/result-first/no-CoT + added a `REFRESH_GUARDRAILS=1` path in `scripts/register_gateway_endpoints.py`); consider a larger judge if it still rambles. Once (a)+(b) land, governed tool-calling can move back onto the Gateway. Relates [[b100-p4-mlflow-gateway]], [[b17-b19-mcp-gateway]].
- **B111** — **Adopt Bifrost as the agentic-lane gateway ("use the whole thing", spun off from B17+B19 Phase 3b)** — Bifrost isn't just an MCP aggregator; it's a full agentic AI gateway (multi-provider LLM egress, **virtual keys + budgets**, **guardrails**, adaptive load-balancing, cluster mode, observability/analytics, 1000+ models — markets as a 50× LiteLLM replacement). **Decision (2026-07-30): go all-in** — consolidate the **agentic lane** onto Bifrost (LLM egress **+** MCP tools **+** VK/budget/guardrail governance in one box), sequenced AFTER the scoped MCP coding-agent edge (Phase 3b) is running. **Evaluate against the two-lane rule** ([[gateway-lane-separation]]): confirm transparent tool-calling passthrough (the thing MLflow failed), per-key budgets replace/augment LiteLLM's spend + valve, VK-scoped tool registries per agent, and observability. If it passes → **retire LiteLLM from the agentic lane** (LiteLLM may still back Bifrost or the MLflow chat lane) and route the operator (B66) + coding agents (B15) through Bifrost. MLflow AI Gateway stays the **chat/eval** lane. This is deliberate consolidation, not shiny-chasing — decide with a bake-off, not vibes. Relates [[gateway-lane-separation]], [[b17-b19-mcp-gateway]], LiteLLM (B26). **▶ IN PROGRESS (2026-07-31):** Phase 3b agent-edge shipped (compositor → Bifrost `/mcp`, 91 tools; `bifrost.weyland.lab`). **Provider load-out** (tracker `aidlc-docs/bifrost-provider-loadout.md`): **8 live** (xAI, Groq, HF, Ollama, OpenCode-Zen, ElevenLabs-TTS, Perplexity, vLLM), 2 paywalled (Cerebras/Parasail — enable behind budget caps), Together parked (Bifrost custom-provider routing bug), Bedrock/Azure/OpenCode-Go skipped. Key finding: Bifrost **auto-injects the 91 fleet tools into every chat completion** (~21k tok) — a FEATURE, not a bug; suppress per-request with empty `x-bf-mcp-include-tools`; Groq is the only tool-free provider (free-tier TPM). **GPU inference bench** (B111 sub-work) — **three-engine GPU serving, each a distinct job:** Ollama=simple single-stream · **vLLM ✅** throughput/continuous-batching (**~15×**, 88.9→1329.5 tok/s conc 1→16, flat latency) · **SGLang ✅** RadixAttention **prefix caching** (**~6.2× faster TTFT**, 26ms vs 164ms miss — the agent/RAG win). PD/prefill-decode disaggregation **REJECTED** (needs ≥2 GPUs; CPU-decode dead on non-AMX i9-13950HX). `nodes/rogueone/services/gpu-inference/` + `scripts/{vllm,sglang}-bench.sh`; DoD-swept (runbook+demo+arch+hosts+api+map+C4), [[gpu-inference-vllm-sglang-b111]]. **DONE this stretch:** provider load-out (15 live / 8 paywalled / 1 parked / 6 skip; Parasail+Wafer since DELETED as redundant), per-provider budget caps (scripted, `register_bifrost_governance.py`), key-sealing (SealedSecret + `env.VAR` keys, 0 plaintext in PVC), **use-case routing → moved to LiteLLM** (NOT Bifrost). Built 9 Bifrost routing rules, then **WIPED** them: Bifrost OSS `chain_rule` is NOT on-failure fallback (proven — down-provider `502 connection refused` + `chain_rule:true` did NOT cascade) and **adaptive load-balancing is Enterprise-locked** (only static routing is OSS); VK `provider_configs` failover IS OSS + transparent but can't resolve self-hosted (vllm/ollama) keys in v1.6.7. So the 9 `wl-*` aliases (`wl-coding`/`wl-agentic`/`wl-rag`/`wl-search`/`wl-reason`/`wl-judge`/`wl-default`/`wl-speed`/`wl-big-oss`) live in **LiteLLM** `k8s/litellm/configmap.yaml` — `model_list` primaries + `router_settings.fallbacks` multi-rung chains (each ends in a free always-on rung; dry paid rungs 402/429 skipped by cost management, not errors). **LIVE + verified**: all 9 route + **fallback FIRES** (forced wl-rag primary-fail → served from groq). Keys via `envFrom bifrost-provider-keys`. `register_bifrost_routing.py` obsolete/removed. Map `docs/llm-routing-map.html`, runbook `model-gateway.md § Use-case router`. Net split: **LiteLLM = router/failover**, Bifrost = MCP edge + egress + budgets + keys + observability, weyland-guard = guardrails (edge), B84/MLflow = evals (offline). **LiteLLM bake-off/retire — KILLED 2026-07-31: LiteLLM RETAINED as-is** (no consolidation onto Bifrost; both coexist — Bifrost = agent edge + provider gateway, LiteLLM stays its lane w/ the egress valve). **DONE 2026-08-01 (Bifrost buildout — this stretch):** (1) **tool-server → FastMCP** (Option C, image v14) — fixed the fastapi-mcp-0.4.0-vs-starlette-1.x `/mcp` hang (`await request.body()` → ClientDisconnect); deps PINNED; compositor `context` upstream re-enabled → **95 fleet tools**. (2) **MCP library** — 9 clients (`register_bifrost_mcp_clients.py`) + in-pod stdio runtime (node+chromium via the initContainer) for Perplexity/Playwright; **VK→client attach = direct DB write** (governance API can't attach runtime-registered clients — `attach_bifrost_vk_mcp.py`, keyed by integer PK, + restart). `coding-agents` VK = **232 tools**, wired into **Claude Code + Codex + OpenCode** (scope-by-use, one shared VK). (3) **Prompt Repository — 241 prompts**: 89 hand-authored (`register_bifrost_prompts.py` — skill-aware system prompts + a `skills` orchestration folder) + 144 corpus-derived (`register_aidlc_prompts.py` — consulting-frameworks/aidlc-stages/industry-lens). (4) **Skills Repository — 583 Agent Skills**: 20 lab-ops/generic + 52 AIDLC stages + 511 KB entries (`register_bifrost_skills.py` / `register_aidlc_skills.py` / `register_aidlc_kb_skills.py`); the proprietary **"Method" brand SCRUBBED** from all distributed skills. **Served as a Claude Code / Codex plugin marketplace** — the gate was a missing **`git`** binary (added to the initContainer), NOT object storage (red herring: config.json MERGES the DB but isn't the marketplace gate); serve routes exempted from Keycloak forward-auth (`/api/skills/serve` open on the MCP ingress). **LIVE:** `claude plugin marketplace add https://bifrost.weyland.lab/api/skills/serve/claude-code/.claude-plugin/marketplace.json`. (5) **Maxim telemetry plugin DISABLED** (was egressing usage to Maxim's cloud — unwanted for a $0/LAN lab). Register scripts are the GitOps-durable source of truth; restore order in `runbooks/mcp-gateway.md`. **DoD-swept 2026-08-01.** **✅ B111 CLOSED 2026-08-03 — tail landed:** (1) **Anthropic ingress** — `/anthropic` drop-in live + VK-guarded (`bifrost.weyland.lab/anthropic`, proven end-to-end); pointing a client at it is a per-client billing choice (Bifrost bills its own key, not a Claude subscription). (2) **Media lane** — image (**Runware** `runware:100@1`) · tts (self-hosted **Kokoro** primary via a `wl-tts` LiteLLM route + Bifrost custom provider `kokoro/kokoro`; **ElevenLabs deferred** — free tier blocks library voices via the API) · video (**Runway** `gen4_turbo`, async submit→poll→mp4; Replicate→Runway fallback). Deploy `k8s/kokoro/` (svc + `kokoro.weyland.lab` UI), durable via `scripts/register_bifrost_kokoro.py`; DoD-swept (loadout/hosts/api/arch/likec4/demos/media-lane.md). (3) **Tool-calling validation** — **7/7 paid providers PASS** transparent tool-calling through Bifrost (anthropic/openai/opencode-zen/xai/deepseek/cerebras/openrouter), confirming the passthrough MLflow's gateway broke; kept as a re-runnable conformance test `scripts/validate_bifrost_tool_calling.py`. See [[bifrost-prompt-repo]] [[bifrost-skills-repo]] [[bifrost-vk-mcp-attach]] [[tool-server-mcp-broken-dep-drift]].

- **B112** — **Track total AI-platform cost in Port.io** — ✂️ **FOLDED INTO B60 (2026-08-05)** — thread (b) of the Port maturity bucket. B111's Bifrost egress now fans out to ~15 paid/free providers (Anthropic, OpenCode-Zen, Perplexity, Cohere, Fireworks, xAI, …), each with its own billing + a Bifrost per-provider budget cap. Need **one cost surface**: pull Bifrost usage (budgets `current_usage` / per-provider + per-VK counters via `/api/governance/*`) into Port as a cost view, alongside the existing **OpenCost (B55)** cloud-cost and the MLflow/LiteLLM spend — so there's a single "what is the AI platform costing" dashboard. Relates B111 (Bifrost budgets), B55 (OpenCost), B43/B59 (Port IDP).

- **B115** — **Guardrails platform (defense-in-depth, 4 paths)** — ✅ **DONE 2026-08-03.** A four-layer guardrails stack, each a distinct path doing one job (the industry-standard pattern; stacks run 2–3, complementary not competing). All OSS/self-host → **$0**. Design: `aidlc-docs/guardrails-platform.md`. Paths: (1) **Scan** = weyland-guard (≈ LLM Guard) — I/O sanitization, already LIVE (B14/B34/B35); (2) **Classify** = **Llama Guard** (Meta), served by **llama.cpp**, **two tiers** — (a) **Llama-Guard-3-1B always-on on CPU (mother)**, the default the Scan layer calls on every classify; (b) **Llama-Guard-3-8B on-demand on the rogueone GPU** (the B111 pattern), the stronger escalation; (3) **Dialog** = **NeMo Guardrails** (adopted from B32) — Colang topical/flow control wrapping the Open WebUI / chat lane, NOT the tool-calling operator (`scripts/nemo-guardrails-trial/`); (4) **Structure** = **Guardrails AI** — output-schema validate + re-ask on structured-output tasks. Compose: Scan (always-on) → Classify → Dialog (conversational surfaces) → Structure (structured outputs); alongside the operator's pre-action-authorization (confirm-rails + `policy.gate`) + offline eval (B84). **Build order:** Llama Guard (first) → Guardrails AI → NeMo → augment Scan. **Progress:** Classify **tier 1 (1B/CPU/mother) DEPLOYED + WIRED + VERIFIED 2026-08-03** — `k8s/llama-guard/` (llama.cpp `QuantFactory/Llama-Guard-3-1B-GGUF:Q8_0`, unmeshed, temp 0), Argo-managed; `scripts/validate_llama_guard.py`. Wired into weyland-guard as validator **`llama_guard.safety`** (INPUT+OUTPUT, **SHADOW**, fail-open) → `LLAMA_GUARD_URL`; guard image **v9** (+httpx dep). Verified end-to-end: `/ready` lists it, pipe-bomb prompt → recorded `block` verdict. **Note:** ~8.6 s cold-KV CPU classify (taxonomy prefix) — fine in shadow (fire-and-forget), and the argument for tier-2 GPU / prefix-cache before any inline promotion. **Tier 2 VERIFIED (on-demand):** `llama-guard-8b` on the rogueone GPU compose (:8003, llama.cpp `server-cuda`, `QuantFactory/Llama-Guard-3-8B-GGUF:Q5_K_M`, `-ngl 99`, temp 0) + wrapper `scripts/llama-guard-8b.sh {start|stop|status|logs|smoke}`; `validate_llama_guard.py` reads `LLAMA_GUARD_URL` for either tier. NOT Bifrost-wired (classifier). **Smoke green 2026-08-03:** benign→safe, pipe-bomb→`unsafe/S9` (the 8B binned it S9=Indiscriminate Weapons vs the 1B's S1 — the sharper call the stronger tier exists for). `-hf` caches to the HF hub layout → shares the `hf-cache` volume. New `scripts/gpu-docker` wrapper = ad-hoc docker on rogueone's native GPU engine (no `DOCKER_HOST` prefix). **Classify path DONE (both tiers).** **Structure path (Guardrails AI) VERIFIED 2026-08-03:** isolated **`guardrails-structure`** svc (`services/guardrails-structure/`, `k8s/guardrails-structure/`, Argo, meshed) — guardrails-ai CAN'T co-install with the Dagster stack (`click<=8.2.0` vs `>=8.4.2`), so it runs alone: FastAPI + `Guard.for_pydantic(JudgeScores).parse` + re-ask via litellm→Ollama; the eval judge (`eval_scores._judge`) calls it through `weyland_pipeline/structure.py` (HTTP client, fail-safe; Dagster image v14→v15). Proven end-to-end: clean JSON → `guarded`, malformed prose → `reasked` (judge repaired it into valid scores). **DoD swept 2026-08-03** (demo + `flow-eval-scoring` sequence + LikeC4 `guardrails-structure` + arch/api/platform-map rows + `GuardrailsStructureDown` alert). **Dialog path (NeMo Guardrails) VERIFIED 2026-08-03:** isolated **`nemo-guardrails`** svc (`services/nemo-guardrails/`, `k8s/nemo-guardrails/`, Argo, meshed) — FastAPI wrapping `LLMRails` → OpenAI `/v1/chat/completions`; Open WebUI adds it as a guarded **`weyland-operator`** chat model alongside the raw Ollama models. Topical control via a strengthened **`self check input`** LLM-judge rail (the Colang dialog/topical flow would NOT fire — v1/v2 answered off-topic, NeMo's finickiest feature, failed the B32 trial too — so topicality moved into the working self-check prompt + a custom refusal message in rails.co). Proven: off-topic → operator refusal, on-topic → answered, jailbreak → blocked (image v3). Gotcha: Open WebUI's OpenAI connection is **PersistentConfig** → the env is ignored on an existing PVC; add it via the admin UI (Settings → Connections) → captured in **B116**. **ALL 4 PATHS LIVE** (Scan · Classify · Structure · Dialog). **NeMo DoD swept 2026-08-03** (new **Concepts → Guardrails** page `docs/concepts/guardrails.md`; `flow-nemo-dialog` sequence; LikeC4 `nemo-guardrails`; demo + UAT; arch/api/platform-map rows [all 4 paths live, none planned]; `NemoGuardrailsDown` alert). **B115 COMPLETE — all four paths live + DoD'd.** Related maturity: **B116** (Open WebUI workspace review). Relates B14, B34, B35, B32 (NeMo adopt), B70 (weyland-guard), B111 (rogueone serving). ⚠️ (renumbered from B113 — that ID is the financial-datasets domain.)
- Plus medium/low: eval-leaderboard frozen, uncodified crons (roadmap-sync, ai_session, docs-site rebuild, code scans), loose `k8s/` root files not in Argo, several stale backlog "done"/count claims.

### B70 — Agentic RAG on LangGraph + LlamaIndex + MLflow tracing — ✅ DONE 2026-07-23 (all 3 parts)
**Added 2026-06-26. Designed + started 2026-07-22** (full design: `aidlc-docs/construction/agentic-rag-langgraph-design.md`). A **LangGraph agentic-RAG loop** — retrieve → grade → *reflect/re-retrieve if weak* → answer — with per-step **MLflow Traces** (`mlflow.langchain.autolog()` + `mlflow.llama_index.autolog()`), more capable than the single-shot `/context/ask`. **Feeds B66** (this is the LangGraph framework-viability spike).

**Architecture (decided):** **LangGraph owns control-flow** (the stateful loop), **LlamaIndex owns retrieval** (4 backends), **MLflow** dual-autologs both → one per-query Trace. New **sibling service `weyland-agent`** (registry image — NOT the tool-server, which stays the stable single-shot path; note the tool-server manifest is actually `:v1`/IfNotPresent, not `:local` as this line once claimed). Generation: LangChain `ChatOpenAI` → Ollama (Phase A) → fold **vLLM** behind LiteLLM (Phase B). Query embedding via rogueone's `rag-embed` (bge-base/768 as of B74, matches the collections).

**Two verified dependency findings (2026-07-22):**
- **Retrieval = CUSTOM LlamaIndex retrievers, not native stores.** The B-RAG-STREAM collections store chunk text under `content` with no `_node_content` blob, so `PGVectorStore`/`QdrantVectorStore` can't reconstruct nodes; the fix is 4 thin `BaseRetriever`s wrapping the tool-server's proven per-backend queries. (Long-term: fix the *writer* to emit LlamaIndex-native schema.)
- **vLLM is Phase B, not free.** LiteLLM today fronts only cloud free-tier (gemini/openrouter), NOT the local box; vLLM is present on rogueone but not serving the RAG model (Ollama is). Phase B = wire LiteLLM→{vllm,ollama} + stand up vLLM on a 16 Gi-fit model.

**3-part build (guard service first — both the tool-server and the agent depend on it):**
- **✅ Part 1 — `weyland-guard`:** the B14 guard layer extracted into a shared FastAPI service (3 typed routes `/guard/{input,output,act}`, SHADOW default, fail-open, models load once ≈1.5 Gi). Live + verified (injection→block, grounding→flag, toxicity→pass in shadow). `services/weyland-guard/`, `k8s/weyland-guard/`, [runbooks/guardrails.md](runbooks/guardrails.md).
- **✅ Part 2 — tool-server migration:** `weyland-tool-server` v0.5.0 drops llm-guard + the guard-model bakes, calls `weyland-guard` over HTTP (fail-open). Verified: `/context/ask` unchanged, verdicts flow via the service (grounding discriminated real-vs-hallucinated), fail-open held (guard@0 → still answers). First clean seam of the tool-server decomposition (→ B31).
- **✅ Part 3 — `weyland-agent`:** the LangGraph loop (retrieve→grade→reflect→generate) + 4 custom LlamaIndex retrievers + dual MLflow autolog, calling `weyland-guard` for outer I/O. Live + verified: `/agent/ask` returns grounded answers, guards flow via the shared service, and **MLflow Traces capture per-step spans** (`agentic-rag` experiment). ⚠️ autolog needs the full `langchain` package (langchain-openai/langgraph only pull langchain-core → silent no-op otherwise). `agent.weyland.lab`; [runbooks/agentic-rag.md](runbooks/agentic-rag.md).

**Completeness gate** applies on build (trigger / lineage=Traces / GitOps / monitoring / docs). **Registry gotcha (hit twice in Parts 1-2):** large-layer pushes to the MinIO-backed registry can stall without finalizing the manifest → `ImagePullBackOff: not found`; re-push, confirm the `vN: digest:` line + `tags/list`, then `rollout restart`.

### B100 — MLflow full buildout: Tracing integrations + Evaluation + Prompts + AI Gateway
**Added 2026-07-23. Phased build in progress: P1 Tracing → P2 Prompts → P3 Evaluation → P4 AI Gateway.** MLflow is deployed (v3.14 — B10/B16/B47: experiment tracking + model registry) and B70 just lit up **Tracing** for `weyland-agent`. But MLflow 3.x is a full **GenAI platform** — this is the B60/B65-style "master the tool" buildout to exploit ALL of it. Four pillars:
- **Tracing (integrations) — ✅ P1 DONE 2026-07-24 (live surfaces).** MLflow auto-instruments a long framework list (OpenAI, LangChain, **LangGraph**, LlamaIndex, DSPy, Anthropic, **LiteLLM**, Gemini, Bedrock, AutoGen, CrewAI…). **Traces now cover all three live AI surfaces:** `weyland-agent` (B70, langchain+llama_index autolog → `agentic-rag`), `weyland-operator` (B66, langchain autolog → `operator`), and the **tool-server RAG `/context/ask`** (B100 — **manual spans**: the generate is a raw httpx→Ollama call, not autolog-able; `context_ask`→`retrieve`/`generate`, exp `tool-server-rag`, `mlflow-skinny`, fail-safe). One pane of per-step GenAI observability (prompt/context/answer/tool spans) the mesh traces (Tempo) can't give. **Eval-harness tracing → folded into B84** (batch, ~360 traces/run — belongs with the eval-observability theme). Coverage table in [runbooks/mlflow.md](runbooks/mlflow.md#genai-tracing-b100-phase-1).
- **Evaluation** — `mlflow.evaluate()` / GenAI LLM-as-judge metrics + the Evaluation UI. **Overlaps the eval harness (B4/B84/B96)** — the current leaderboard is a custom Dagster matrix + judge panel. Decide: migrate/consolidate onto `mlflow.evaluate`, or run alongside (MLflow eval = GenAI-native path; the golden set B96 = the fixed exam).
- **Prompts — ✅ P2 DONE 2026-07-24 (live surfaces).** MLflow **Prompt Registry** — inline strings promoted to versioned, hot-swappable prompts. **4 registered** (`@production`): `rag_system` (shared by tool-server `/context/ask` + agent generate), `operator_system`, `agent_grade` + `agent_reflect` (templated). Source of truth = `scripts/register_prompts.py` (idempotent sync); services fetch via a shared `prompts.py` — `load_prompt`/`render_prompt`, **TTL-cached** (default 300s) so a version bump hot-swaps with **no redeploy**, **fail-safe** to a baked fallback. API on the `mlflow.genai` namespace (present in `mlflow-skinny`). Eval judge prompt → folds into **B84**. Doc: [runbooks/mlflow.md](runbooks/mlflow.md#prompt-registry-b100-phase-2).
- **AI Gateway — ✅ P4 DONE 2026-07-25.** MLflow 3.14's **built-in** AI Gateway (DB-backed, in the tracking server — NOT the deprecated standalone CLI): a governed OpenAI-compat front door over **17 endpoints** (6 local Ollama + 9 hosted + 2 judges), with **LLM-judge guardrails** (Safety AFTER/block + PII BEFORE/sanitize) and a **GLOBAL budget** ($10/mo REJECT). **Fully codified + self-healing** in `scripts/register_gateway_endpoints.py` (endpoints→secrets→model-defs→scorers→guardrails→prune-stale→attach→budget, one idempotent run; keys via gitignored `scripts/.env`), verified by `test_gateway_guardrails.py` + `eval_gateway_models.py` (`mlflow.genai.evaluate` over the gateway — modernizes B84's legacy `mlflow.evaluate`). **Does NOT replace LiteLLM (B26)** — LiteLLM stays as one *included* option; the gateway is the MLflow-native plane. **Headline finding:** an LLM guard puts the judge in the critical path and fails **closed**, so judge choice is a real trade — Gemini free-tier (20 RPM) → quota-fails the whole gateway; llama3.2:3b → too eager (false-blocks benign); **qwen2.5:7b = the local, no-quota sweet spot**. Enablement = `mlflow[gateway]` extras in `k8s/mlflow/mlflow.yaml`. Runbook [runbooks/mlflow-gateway.md](runbooks/mlflow-gateway.md), demo [demos/mlflow-gateway.md](demos/mlflow-gateway.md). **B100 = DONE** (P1 tracing + P2 prompts + P4 gateway; P3 eval → B84).
- **Sequencing:** Tracing integrations first (immediate observability win, low-risk). Eval / Prompts / Gateway are each an *evaluate-and-decide against an existing tool* (eval harness / LiteLLM) — spikes, not just installs. Feeds B84 (LLM Eval & Observability) + B70/B66.

### B101 — Registry manifest-finalization defect (large pushes don't land the manifest) — ✅ MITIGATED 2026-07-24
**Added 2026-07-23.** `docker push` to the MinIO-backed OCI registry (`registry.weyland.lab`, `distribution/registry`, blobs on the uas-quirked USB disk) completes the blob layers but **intermittently fails to finalize the manifest PUT** → the tag is absent and the pod `ImagePullBackOff`s with `not found` even though the blobs are present. A re-push (blobs already there = fast) re-sends the small manifest, which lands. **Hit 3× in one session** (weyland-guard, tool-server v2, weyland-agent v1→v2), costing a round-trip per deploy. Investigate: the registry→MinIO manifest-write path (USB-disk latency? a registry storage/timeout config?), any remaining Traefik/ingress limit (readTimeout=0 fixed the 60s *read* cut, but the manifest PUT may hit a different one), or wrap pushes in a **verify-and-retry** helper (`push → curl tags/list → re-push if missing`) as the pragmatic mitigation. **Done 2026-07-24 — `scripts/push-image.sh <ref>`:** pushes, verifies the tag is in `/v2/<name>/tags/list`, and auto-re-pushes if not (`PUSH_ATTEMPTS`, default 3) → a deploy is one command. Root cause = the USB/S3 manifest-write race (no registry timeout/consistency knob exposed in `k8s/registry/registry.yaml`); accepted as a lab constraint. Runbooks' raw `docker push` can adopt the wrapper (operator.md updated). See [[traefik-readtimeout-registry-push]], [[weyland-usb-uas-quirk]].

### B102 — Automate prompt registration (register_prompts.py → Dagster asset) — Maturity
**✅ DONE 2026-08-02.** Shipped as the Dagster **`registrations`** group (weekly + on-demand `registrations_reconcile_job`,
auto-running): `bifrost_prompts_registered` + `bifrost_skills_registered` (shell out to the register scripts bundled in
the user-code image) + `realm_roles_registered` (pulls the Realm `GET /prompts` → registers `role-<key>` in Bifrost, so
the Realm stays the source of truth). All idempotent → the Bifrost prompt/skill repos + realm roles self-heal after a
PVC/store reset with no manual `kubectl exec`. **MLflow prompt-reg (`register_prompts.py`) intentionally stays a runbook**
— `mlflow` isn't in the Dagster env and folding it risks the dagster+dbt+datahub version clashes the image avoids
(candidate for its own CronJob in the mlflow image later). realm-of-agents v17 (`/prompts`), user-code v14.

**Added 2026-07-24.** B100 P2 shipped the MLflow Prompt Registry with `scripts/register_prompts.py` as the source of
truth, run **manually on change** (`kubectl -n weyland exec -i deploy/weyland-agent -- python < scripts/register_prompts.py`).
Mature it into a **Dagster asset** so registration is GitOps-reproducible + auto-synced like the rest of the mesh: an
idempotent asset (a new `prompts` group, or fold into an existing group) that reads the canonical templates and
registers/aliases them to MLflow — on-demand + scheduled (or triggered on repo change once B30's push-trigger lands).
**Payoff:** prompts survive an MLflow store reset with no manual step, and prompt edits flow through the pipeline like
every other artifact. **Low priority** — manual re-run is fine for a solo lab with infrequent prompt edits; the
services fail-safe to baked defaults regardless. Extends **B100**.

### B103 — Langfuse LLM observability (deferred from B84 P3) — ✅ DONE 2026-08-11 — deploy + emitter + prompt-federation Ph1+Ph2 + session-grouping + online-evals (Scores/Evaluators/Datasets/Annotation) all shipped
**Deploy + emitter DONE 2026-08-09.** Langfuse v3 self-hosted, **reuse-first** — only the stateless **web + worker** pods
(`k8s/langfuse/langfuse.yaml`, Argo `subdir-apps.yaml`); every stateful plane reuses an existing lab service
(Postgres `langfuse` DB · ClickHouse `langfuse` DB, `CLUSTER_ENABLED=false` · Valkey queue · MinIO `langfuse` bucket).
This voids the original "won't schedule" note below — the marginal cost is ~web+worker, not a dedicated ClickHouse
stack, and mother grew to 78 Gi. UI `langfuse.weyland.lab` (Keycloak forward-auth). **First emitter wired: LiteLLM**
(`callbacks: ["prometheus","langfuse"]`, in-cluster `LANGFUSE_HOST`) — traces (model/tokens/latency/per-VK) verified
landing in the `weyland-platform` project. Deploy/wiring gotchas (OOM exit-134 vs 137, Redis no-auth connection-string,
worker port, cherry-picked `env` vs blanket `envFrom`, key-mismatch) captured in memory `b103-langfuse` + runbook.
**Remaining IN SCOPE (part of B103 — NOT separate B-numbers):** (1) **prompt federation — Phase 1 ✅ DONE (2026-08-10):** Bifrost = single SoT (269 prompts,
incl. the 4 app prompts migrated into `app-integrated`); `sync_prompts.py` mirrors Bifrost → Langfuse + MLflow (REST —
the langfuse SDK's `packaging<26` conflicts with the dagster lockfile); prompt↔trace linkage LIVE on tool-server
(v16) + operator (v21) + agent (v5) via a per-app `_lf_generation` (Langfuse v4 SDK, `prompt=` link → each trace shows
`Prompt: <name> - vN`). Design `aidlc-docs/prompt-federation-design.md`, memory `prompt-federation-b103`. **Phase 2 ✅ DONE (2026-08-10) — bidirectional + auto:** `sync_prompts.py` runs
`reconcile_inbound()` FIRST (native Langfuse/MLflow edits → Bifrost), then mirrors outbound; loop-safe via content-hash
+ `synced-from-bifrost:<hash>` stamp, conflict = last-write-wins by timestamp. Wired as the `prompt_federation_synced`
asset in the Dagster `registrations` group (downstream of `bifrost_prompts_registered`; user-code img v41) → runs on
the weekly/on-demand reconcile, no manual exec. **Gotcha:** native-edit detection keys on the VERSION-level
`commitMessage`, NOT Langfuse `tags` (tags are PROMPT-level/sticky → a native edit inherits v1's stamp → would be
falsely skipped). (2) **Langfuse online evals — ✅ DONE 2026-08-11.** All four shipped: **Scores** + **9 native
evaluators** (7 managed + custom citation/refusal) created programmatically via `/api/public/unstable/evaluation-rules`
(NOT `/eval-configs`=404), live per-trace on `rag-generate`, $0 on `wl-judge-oss`; **Datasets** = git `eval_sets/` SSOT
(golden.json = B96, regression.json = Promptfoo gate) mirrored to `weyland-golden`/`weyland-regression` by
`langfuse_eval.py`; **Human Annotation** = `weyland-rag-review` queue + `human_quality` score-config. Codified as
`registrations` assets (dagster v43) → DB-reset-durable. SSRF fix = `LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST`. Memory
`langfuse-evaluation-b103`; design `aidlc-docs/langfuse-evaluation-design.md`. — Evaluators (LLM-as-judge on a sampled
slice of `platform` production traces) + Annotation Queues + Datasets; point Datasets at the [B96] golden set so the
offline ([B84]) and online eval lanes share fixtures. These are the online/ prompt complement to the offline suite —
the net-new capability the eval flagged. Original deferral rationale kept
below for history. **(3) DOCS follow-up — ✅ DONE 2026-08-11:** two comprehensive `docs.weyland.lab` concept pages
shipped — **`docs/concepts/federated-prompts.md`** and **`docs/concepts/federated-evals.md`** — each covering the
**SSOT** (prompts = Bifrost repo; eval fixtures = git `eval_sets/*.json`), the **tools** and an **ownership matrix**
(Bifrost owns prompt authoring → Langfuse/MLflow are mirrors; git owns eval fixtures → Langfuse Datasets mirror;
Langfuse owns online scoring; MLflow owns the offline leaderboard; LiteLLM owns the judge model; Promptfoo owns the
regression gate), **what each tool does**, and **what makes them different** (offline-vs-online, benchmark-vs-gate,
source-vs-mirror) — each with a mermaid flow + gotchas. Auto-nav (no `nav:` in `mkdocs-site.yml`) picks them up under
**Concepts**; LikeC4 model re-validated (`✓ Valid`). Renders after push + docs-site rebuild.

**Added 2026-07-25.** B84 originally scoped **Langfuse** as the OSS LLM tracing/observability tool. **Deferred to
maturity** after the P2 wrap — two reasons: (1) **its original justification is spent.** Langfuse was scoped to fill
"nothing traces the LLM path"; **B100 P1** (MLflow Tracing) already traces all three live AI surfaces (agent / operator
/ tool-server RAG) at span level. Overlap is ~80% — Langfuse would be a *2nd* tracing backend, a *3rd* prompt store
(vs B100 P2 registry), and a *4th* eval surface (vs the B84 3-lane suite). (2) **node capacity.** The k3s cluster is
**single-node** (mother, 64 GB); memory *requests* are already at **~93%** (~4.7 Gi headroom, 2026-07-25) — Flink/eval
suite/etc. backfilled the B79 grow. Langfuse v3's heavy component is **ClickHouse**: the reuse path (web+worker on the
existing CH/Valkey/PG/MinIO) is ~1.5–2 Gi (fits but lands the node at ~96% requests — thin, and swap is off/B99); a
**dedicated ClickHouse** (recommended for trace write-volume) is ~4–6 Gi and **won't currently schedule**. **The one
genuinely net-new capability** = **online eval on *production* traces** (continuous LLM-as-judge + annotation queues) —
the whole B84 suite is offline/golden-set. **Revisit when:** node headroom grows *and* continuous production-trace
scoring becomes a real need — and even then, first check whether **MLflow 3.14 `mlflow.genai` trace assessments/feedback**
covers it in the tool already run (one pane of glass) before standing up a parallel platform. Decision context:
[demos/eval-lanes.md](demos/eval-lanes.md). Deferred from **B84**.

### B71 — DataHub domains + ownership (governance pass)
**Added 2026-06-26.** The catalog has datasets but **no domains, no ownership** — and domain-oriented ownership is the *organizing principle* of the data mesh (part of B1's governance layer alongside Keycloak/Ranger/OPA/Soda). Promote the existing **Dagster groups** (already emitted as `dagster_group` tags: default/RAG, eval, catalog, aidlc_kb, ai_session) into real DataHub **Domains** (likely consolidated — *RAG Platform · Eval · Model Catalog · Knowledge Base*), and assign **ownership** (a "Weyland" group / emangini as Technical Owner). Apply three ways (mix):
1. **Ingestion recipes** — `domain:` (pattern→domain) + `owners:` config so the pull sources (Postgres/Grafana/Neo4j/MLflow/Iceberg) auto-file on every run.
2. **`datahub_emit.py`** — extend to emit Domain + Ownership for the Dagster assets (the group→domain mapping is half-built since we already emit the group tag).
3. **csv-enricher ([B68])** — bulk-assign domains/owners/tags to existing entities from a CSV/Sheet. A **URN → domain → owner** mapping *is* the "sheets" B68 was blocked on — so B71 unblocks/uses B68.
- Makes everything cataloged this session (Dagster/Grafana/Iceberg/MLflow/Neo4j/Postgres) navigable. Strong candidate to do next.

### B75 — Additional music datasources — 🟡 MEDIUM (2026-08-05; data expansion)
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

### B76 — Full MSD + Music4All + MTG-Jamendo — 🟡 MEDIUM (2026-08-05; data expansion)
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

### B84 — LLM Eval & Observability (model-eval product + Promptfoo + Langfuse)
**✅ P1 (model-eval product) DONE 2026-07-24.** The B4/B96 judge-panel leaderboard is now a first-class **DataHub Data
Product** (*Model-Eval Leaderboard*, ML & Modeling domain, 9 eval datasets, **owned** by emangini) with a validity +
freshness **Data Contract** on `eval_scores` (native assertions via `emit_eval_assertions`), a **Superset dashboard**
(`superset.weyland.lab/superset/dashboard/15` — per-model bars + faithfulness trend), a **Resources link** from the
product, and a **Port** `endpoint` launcher. All reproducible (`datahub_emit.py` `_PRODUCTS`/`_PRODUCT_LINKS`/
`emit_eval_assertions`; Superset defs). Demo: [demos/model-eval-product.md](demos/model-eval-product.md).

**✅ P2 (eval engines) DONE 2026-07-25 — kept as a *complementary suite*, NOT a bake-off.** The "pick one engine" framing
was wrong: the three passes answer three different questions, so all three ship. (1) **Judge panel** (B4/B96) — the
canonical *ranking* (golden 20Q × 6 models, ≥3 judges averaged, sliceable, productized in P1). (2) **`mlflow.evaluate`**
(`scripts/eval_mlflow_evaluate.py`) — the GenAI-native *surface*: re-scores the panel's stored answers with MLflow genai
metrics (single local judge) into the `mlflow_evaluate` experiment + Evaluation UI; legacy API (deprecated 3.4 → modern
`mlflow.genai.evaluate` on adoption). (3) **Promptfoo** (`k8s/promptfoo/`, always-on `promptfoo.weyland.lab`, $0
self-hosted) — the fast *regression gate*: declarative model×prompt matrix over live `/context/ask`, deterministic +
`llm-rubric` (local judge) assertions, exit-100 CI semantics, honest-negative test; caught `qwen3:14b`'s data-mesh
conflation on first run. Also folded in: **eval-tracing** (B100 P2a — judge-panel spans → `eval` experiment) + the
**eval judge prompt**. Decision ref: [demos/eval-lanes.md](demos/eval-lanes.md).

**P3 (Langfuse) DEFERRED → maturity (`B103`), 2026-07-25.** Original gap (LLM-path tracing) already closed by **B100 P1**
(MLflow traces all 3 live AI surfaces); ~80% overlap + a single-node at ~93% memory requests → not worth a parallel
platform now. Revisit for the one net-new (online eval on *production* traces) when node headroom grows — checking
`mlflow.genai` trace assessments first. Rationale in `B103`. **B84 = DONE** (P1 + P2 delivered; P3 spun out).

**Added 2026-07-16.** Spun out of the **B1.9 reframe** — the mesh's "3 data products" collapsed (9 already exist), and only *model-eval* was worth a real build. One coherent LLM-eval-and-observability theme; all three OSS / self-hosted / **$0**.
- **model-eval — the judge-panel leaderboard, as a first-class mesh *data product*.** NOT net-new logic: **B4** already built the pipeline (testset → run-matrix → **3-judge panel** → `eval_leaderboard` over RAG × 6 models; `gpt-oss:20b` the defensible pick). This *productizes* it — catalog the leaderboard as a DataHub Data Product under **ML & Modeling**, give it a contract + freshness, and expose it (Port / Superset) so "which model wins, on what, as of when" is a governed browsable asset, not a Dagster table. Optionally re-engine the hand-rolled judge loop on Promptfoo.
- **Promptfoo** — OSS LLM eval / red-team harness (declarative test matrices, model-vs-model, assertions, prompt regression). Candidate **engine** for model-eval + a standalone prompt-regression gate for the tool-server / Hermes prompts. Self-hostable CLI + web UI, $0.
- **Langfuse** — OSS LLM **tracing / observability** (traces, spans, token/cost, prompt versions, eval scores). The LLM-native observability gap: GlitchTip catches errors and Prometheus catches infra metrics, but nothing traces the *LLM* path (Hermes → LiteLLM → model; RAG retrieve → rank → generate). Self-hosted on Postgres + ClickHouse (both already in the lab), $0.
- **Sequencing:** model-eval first (rides the done B4 + mesh) → Langfuse (instrument Hermes / tool-server / LiteLLM) → Promptfoo folds in as the model-eval engine or a CI-style prompt gate. Its own brainstorm when reached.

### B85 — data-store-mageddon v2 — 🔴 HIGH (2026-08-05; comprehensive datastore re-evaluation; ↑ Medium→High 2026-08-08 rebalance — the disk-stall/timeout incident (B123) makes a systematic datastore re-eval more earned)
**Added 2026-07-16.** A full re-sweep of candidate datastores, **superseding B67** (dropped candidates) **+ the B65 Tier-3 "keepers" re-eval**. Same bar as v1: **$0 / no cloud-paid, single-node-feasible, non-redundant with the committed grid, earns its keep as a *new capability*** (breadth-for-learning counts; catalog-clutter does not). 27 stores, four verdicts:

**✗ Cloud / paid / proprietary — can't or won't run ($0 + LAN-only):**
- **BigQuery**, **DynamoDB** — cloud SaaS, billed, no LAN footprint.
- **Okta** — SaaS IdP; **Keycloak** owns identity and a LAN can't depend on cloud auth (B1.1).
- **Vertica**, **Exasol**, **SingleStore**, **Denodo**, **MimerSQL**, **OpenEdge** — proprietary cores (some ship capped free/community single-node tiers, but the engine is closed + carries enterprise baggage, and each is redundant with what we already run).

**✗ Already declined with recorded rationale (pure duplicate of the committed stack):**
- **Airflow** → Dagster (orchestrator) · **Airbyte** → dlt + Debezium (EL/CDC) · **Metabase** → Superset + Lightdash (BI; design said "No Metabase") · **InfluxDB** → TimescaleDB (design said "no InfluxDB") · **Spark** → Ray + Flink + Trino + dbt (compute/transform) · **Yugabyte** → CockroachDB (already the distributed Postgres-wire NewSQL).

**~ Marginal — real OSS, but redundant / heavy for near-zero new capability on one node:**
- **Doris**, **Druid**, **Greenplum** — real-time / MPP OLAP; overlap **ClickHouse** (committed); all multi-process (Druid is the heaviest thing on either list). · **Dremio** — federation, overlaps **Trino** + **Cube**; the closest "reconsider first" of this bucket (reflections/acceleration). · **TiDB** — MySQL-wire NewSQL HTAP; heavy (PD + TiKV + TiFlash). · **Hive**, **Phoenix** — Hadoop-era, need HDFS / HBase; **Nessie + Iceberg** supersede the metastore/warehouse role.

**✓ Genuine new-category candidates (free, single-node-feasible, a slot the grid lacks):**
- **RDF / triplestore (Apache Jena Fuseki)** — **top pick.** SPARQL / semantic-web graph is a genuinely *different* model from Neo4j's property graph, it's lightweight, and it ties straight to the AIDLC-KB + glossary (the taxonomy is inherently triple-shaped). The one clear gap.
- **Apache Ignite** — in-memory data grid + SQL; a distinct category from Valkey-as-cache.
- **Tarantool** — in-memory DB + Lua app-server; a curiosity.
- **Derby**, **Firebird** — light embedded / legacy OSS RDBMS; trivial to stand up, mostly "grid completeness," low incremental value.

**Recommendation:** graduate **RDF / Fuseki** to a real build when a semantic-graph / SPARQL need surfaces (the KB taxonomy is the natural trigger); keep **Ignite / Tarantool / Derby / Firebird** parked-but-recorded (available, not committed); treat the **✗** and **~** buckets as **closed with rationale** so they aren't re-litigated. **Re-eval trigger** (as B67): a concrete need the committed stack can't meet.

### B86 — Evaluate spec-driven dev frameworks: OpenSpec · Spec Kit · BMAD · Kiro (vs the Method/AIDLC) — ✅ DONE 2026-08-11
**Added 2026-07-17.** Compare four external **spec-driven / agentic-development** approaches against the project's own AIDLC **Method** (`.methodaidlc/`, the user's own IP — see [[methodaidlc-user-authored]]):
- **OpenSpec** — open spec format + workflow for spec-first AI coding (change proposals → specs → implementation, agent-agnostic).
- **GitHub Spec Kit** (`spec-kit`) — GitHub's spec-driven toolkit (`/specify` → `/plan` → `/tasks`), agent-agnostic CLI.
- **BMAD-METHOD** — "Breakthrough Method of Agile AI-Driven Development": role-agents (analyst / PM / architect / dev / QA) + sharded PRD/story docs, two-phase (planning → dev cycle).
- **Kiro** — AWS's agentic IDE with a built-in spec flow (requirements → design → tasks) + steering files + agent hooks.
**Goal:** map what each does, where they overlap/diverge from the Method's stages (validated-intent → requirements → design → construction → operations), and whether any patterns/artifacts/tooling are worth adopting into — or cross-pollinating with — the Method. **Output** = a comparison doc + decision matrix (`docs/concepts/` or `aidlc-docs/`). Research/maturity item — evaluate first, no commitment to adopt. All four are free/OSS or free-tier, so $0-friendly to trial.

**✅ DONE 2026-08-11.** Four parallel web-research passes → comparison doc + decision matrix at `docs/concepts/spec-driven-frameworks.md` (published, committed). **Finding:** the four externals are *coding workflows* clustered in requirements→implementation; the Method is a *delivery-lifecycle superset* — it owns the discovery front-end (Opportunity Framing → Validated Intent) **and** the operations/telemetry → continuous-discovery loop that none of them touch. **Decision — cross-pollinate artifact notations, do NOT migrate:** borrow (1) OpenSpec **delta specs** (ADDED/MODIFIED/REMOVED) → the Method's Iteration-N delta; (2) Spec Kit **constitution + `analyze` consistency gate** → a checkable baseline; (3) Kiro **EARS notation** → Requirements Analysis (+ steering-file pattern); (4) BMAD **context-engineered story/unit files**. **Kiro disqualified as a tool** ($0 violation — managed AWS, Bedrock-locked, no BYOK, capped free tier). Optional follow-up: trial OpenSpec or Spec Kit on one small unit ($0/MIT/reversible). Memory `spec-driven-frameworks-b86`.

### B87 — Vet + live-validate all E2E demos (E1–E12) — 🔴 HIGH (2026-08-05; maturity pass; ↑ Medium→High 2026-08-08 rebalance — refill High after closing B106; DoD-aligned anti-fabrication QA)
**⏸ DEFERRED 2026-07-20.** Deliberately batched: validate **all** demos in one sweep once the core build is done, rather than re-validating piecemeal as each new capability churns the demos underneath. Trigger: end of the core work (the demos stay 🟡 until then, which is the honest state — not a gap being ignored).

**Added 2026-07-17.** The 12 end-to-end walkthroughs (`docs/demos/*-e2e.md` + `soda-dq.md` / `ranger-masking.md`; ledger rows **E1–E12** in `docs/demos/README.md`) are **🟡 authored, pending a live validation run**. Per the demos DoD a demo isn't ✅ until it's been executed **straight through against live infra**. This item = the last mile of the docs-relevance + E2E-demos pass, and the tracker for it.
- **Run each E2E demo end-to-end** (UI + CLI) on the live platform; flip 🟡 → ✅ in the ledger as each passes.
- **Resolve the inherited `TODO: verify` markers** (full list in `demos/README.md` → Outstanding): eval FK column · datahub emit-token secret name · `model_catalog` columns · MLflow 3.14 delete CLI · in-pod `dagster asset materialize -m` invocation · `genre_classifier` feature columns/order · `/context/search` body · consumer-group deletion · roadmap field mapping · etc.
- **Fix any command that doesn't run as written** (drift between the demo and live behavior).
- **+ row 47 `aidlc-workflow.md` Part B (added 2026-08-20, B133).** Not an E2E walkthrough, but the identical state — authored, unexecuted — so it batches here rather than blocking B133. Runs `/aidlc --scope bugfix` against a **disposable `/tmp` fixture** the demo creates and tears down (a shell script that divides by zero on an empty file; defect reproduction **verified** 2026-08-20). Part A (engine validation) is already RUN. Validating Part B means sitting through ~4 approval gates — it **cannot be run unattended**, since every stage ends in a human turn-stop. Scope note learned the hard way: use a scope that **skips discovery** (`bugfix`/`refactor`/`express`/`infra`/`security-patch`/`classic`/`workshop`); `poc`/`feature`/`mvp`/`enterprise` pull in `intent-capture`, which asks *what business problem is this solving* — unanswerable for a fixture, and it stalled the first attempt.
- Covers the two open threads from the E2E batch: the live-validation of the demos + a single tracked home for the whole unit (this row + Linear).

---

### B88 — Per-language test runners on Woodpecker — 🟡 MEDIUM (2026-08-05; gated on Stud.IO CI track, B57/B118)
**⏸ DEFERRED 2026-07-20.** Woodpecker is **idle** — nothing in the lab currently drives it, so building per-language runners now would be capability-for-its-own-sake. **Trigger to revisit: when Stud.IO starts using weyland's build pipeline** (Woodpecker was always intended as the shared build farm — see the B56/B57 Stud.IO-migrates-on-later note). Scope below stands as written for whenever that lands.

**Added 2026-07-18.** The B69 weekly scans (`scan-suite` + `sonar-scan`) are **quality gates** — static/security/hotspot analysis, no code execution. The missing sibling is **test execution**: Woodpecker CI pipelines that actually build + run the test suites per language (Python/pytest, Java/Maven for the Flink modules, shell, etc.) so regressions are caught, not just smells. This is the LAN-native answer to "no GitHub Actions" ([[lan-no-github-webhooks]]) — Woodpecker polls/triggers in-cluster.
- Stand up language-specific runner images/pipelines (start with pytest for `weyland_pipeline` + `mvn test` for `k8s/flink/*`).
- Wire results into the same surfaces the scans use (Port `code-quality` / a test-results webhook) so pass/fail trends live alongside the quality gates.
- Trigger model matches the rest of the LAN lab: cron/poll or manual, not push webhooks.

---

### B89 — Drive the scan-suite findings to zero — ✅ DONE 2026-07-18
**✅ DONE 2026-07-18.** Triaged all 6 scanners — **2 real fixes shipped, the rest phantom-or-accepted (real deployed vulns ≈0)**: gitleaks 1C→0 (Kiali signing key → SealedSecret), bandit 6H→0 (MD5-for-IDs → `usedforsecurity=False`), semgrep 4H→0 (sealed-ciphertext FP excluded), trivy 204H→2-tracked (193 readOnlyRootFS + 8 intentional accepted in `.trivyignore`; ranger creds→B92, trino FP), osv 56H→0-real (4 Flink-transitive accepted in `osv-scanner.toml`; 52 unpinned-dep phantoms proven via `pip freeze`→B91), kubescape 6H→0-new. GIT-0003 fixed (`vulnerability_alerts=true` in repo.tf). Follow-ons logged: B91 (dep-pinning), B92 (ranger creds), B93 (memory limits). Original scope below.

The B69 weekly `code-scan-suite` surfaces the issue backlog across 9 tools in Port `security_scan`. This was the remediation pass (the B47 SonarQube/Trivy fix, but suite-wide). Work criticals → highs first:
- **gitleaks `1 Critical` = a committed secret on a PUBLIC repo** — triage FIRST; if it's live, rotate + purge from history. Highest priority regardless of the rest.
- **osv-scanner 56 High** (dependency CVEs) + **trivy 204 High / 245 Med** (vuln/misconfig/secret) — the bulk; likely overlaps the B47 accepted-residuals (`KSV-0118`/`KSV-0014` readOnlyRootFilesystem). Re-triage: fix or document-and-`.trivyignore` each.
- **semgrep 4 High**, **bandit 6 High**, **kubescape 6 High** — code + workload hardening.
- Track the counts trending down in the Port `security_scan` view run-over-run; the weekly cron is the regression guard.

### B90 — Build out the Code Quality Port surface (code-maat + Sonar detail) — ✅ DONE 2026-07-18
**✅ DONE 2026-07-18.** code-maat hotspots now flow to Port via a new **`code_hotspot`** blueprint (`tofu/port/blueprints.tf`) + a `scan.py` top-20 POST (`kind:"hotspot"` discriminator) + a 3rd webhook-mapping entry. Built the **Code Health** dashboard (Port MCP `upsert_dashboard_page`, Port-only — dashboards aren't codifiable): Σ critical / Σ high / Σ medium number cards (security_scan) + a Quality-Gate table (code_quality) + a Top-Hotspots table (code_hotspot, sorted by churn). **Caveat:** Port holds SonarQube's *gate* (native webhook), not per-issue detail — the Ocean `sonarQubeIssue`/`Project` blueprints are empty (no Ocean integration runs against the LAN SonarQube); wiring per-issue sync would be its own task. Original scope below.

Today the `code_quality` blueprint holds only SonarQube's `qualityGate`. Made the Code Qualities page the real code-health surface:
- **code-maat hotspots → Port** — scan.py currently only *logs* the change-hotspots (`entity,n-revs`); add a Port POST (new `code_hotspot` blueprint or a hotspots array on `code_quality`) so the CodeScene-style behavioral data is visible/queryable, not buried in a pod log.
- **Richer SonarQube** — surface bugs/vulns/code-smells/coverage/duplication measures (Port already has SonarQube Issues/Projects catalog tables via the Ocean integration — wire them together on one page).
- Goal: one Port view answering "where is the risk + churn" — pairs with B89 (findings) and B88 (test runners).

### B91 — Pin Python deps to lockfiles (reproducible builds + accurate scans) — ✅ DONE 2026-07-19
**✅ DONE 2026-07-19.** pip-tools split applied to all 5 services: the loose `requirements.txt` → `requirements.in` (human top-level), and a **pinned `requirements.txt`** captured from each service's real `pip freeze` (weyland-dagster 310, genre-trainer 124, rag-embed 70, rag-index 38; store-scaler was already 3/3). Dockerfiles unchanged (they install `requirements.txt`, now pinned). weyland-dagster + rag-index rebuilt clean from the pins; rag-embed/genre-trainer freezes came from working envs (installable by construction). **osv-scan of the pinned services = "No issues found"** — the ~52 phantom highs are gone (osv now reads real versions) and no genuine CVE surfaced. No image re-roll needed (the running images already match the pins); future builds are now reproducible. Original scope below.

The service `requirements.txt` files were **unpinned** (only `mlflow-skinny==3.14.0` pinned). Two costs: (1) **non-reproducible builds** — a rebuild resolves different versions (the exact env-parity pain from [[remote-training-rogueone]]); (2) **osv-scanner reads no version → `0.0.0` → matches every historical CVE**, manufacturing ~52 phantom "High" findings (B89 verified them phantom: scanning the running pod's `pip freeze` = "No issues found" across 310 packages). The fix, per service (`weyland-dagster`, `rag-index`, `rag-embed`, `genre-trainer`, `store-scaler`):
- Capture the built image's `pip freeze` → commit as a `requirements.lock` (the freeze IS the lockfile).
- Build the image FROM the lock (`pip install -r requirements.lock`); keep the loose `requirements.txt` as the human-edited top-level, regenerate the lock on intentional bumps.
- Preserve the deliberate co-resolution (e.g. dagster + dagster-dbt unpinned together) — the lock freezes the *resolved* set, not the intent.
- Net: osv-scanner sees real versions (phantom highs vanish), and builds become reproducible. Verify each image still builds + runs from its lock before committing.

### SEC-1 — Move inline dev creds out of manifests into Secrets — ✅ DONE
General security pass (same class as B92/B97): relocate inline/plaintext dev credentials out of committed k8s manifests into Secrets so nothing sensitive lives in the public repo. Tracked in Linear as EMA-84. Related follow-ons: B92 (Ranger creds → SealedSecret), B97 (n8n key untrack+rotate), B95 (hardening-collision guard).

### B92 — Relocate Ranger's committed dev-passwords to a Secret — ✅ DONE 2026-07-20
**✅ DONE 2026-07-20.** All **9** non-empty passwords moved out of the `ranger-admin-install` ConfigMap into a **`ranger-admin-secret` SealedSecret** (data-mesh) — values preserved, no rotation, so the DB/admin creds still match and nothing was disrupted. The ConfigMap now ships only `@@TOKEN@@` placeholders; a **`render-install-props` initContainer** copies the template + `sed`s each token from `envFrom` the secret into a writable emptyDir the main container mounts as `key/` (the ConfigMap mount is read-only, so it can't be sed'd in place). Verified: `deployment "ranger-admin" successfully rolled out` and the rendered file shows the real values (`db_password=weyland_dev_password`, `rangerAdmin_password=Weyland_dev_password1`).
**Bonus fix:** the rollout exposed that `weyland/ranger:2.6.0-py3` was a **local ctr-import never pushed to the registry** (a missed B69 Wave 3 case) and had been pruned off the node — Ranger couldn't restart at all. Built + pushed `registry.weyland.lab/ranger:2.6.0-py3`, repointed both containers, and added a version-pinned ranger line to `scripts/build-push-images.sh` so it survives future prunes.
`KSV-0109` is now blanket-accepted in `.trivyignore` — both remaining hits (ranger placeholders, trino `${ENV:...}` refs) are true false positives. Original scope below.

trivy `KSV-0109` caught what gitleaks missed: `k8s/data-mesh/ranger.yaml`'s ConfigMap holds **plaintext passwords in the public repo** — `db_root_password=weyland_dev_password`, `rangerAdmin_password=Weyland_dev_password1`, `rangerTagsync_/rangerUsersync_/keyadmin_password`, etc. They're the shared LAN dev password ([[lab-dev-credentials]] — low real risk), but committing them violates "creds via Secret, never committed," same class as the B89 kiali fix.
- Bigger lift than kiali: Ranger reads these from `install.properties`, so relocating means reworking how the setup consumes them (env-refs from a SealedSecret, then the setup script/`ranger_setup.py` reads env) — see [[ranger-trino-authz-b-l5]] for the config mechanics.
- Once relocated, the `KSV-0109` note in `.trivyignore` can flip to a blanket ignore (only trino's false-positive would remain).
- Consider whether to rotate `Weyland_dev_password1` off the shared value while at it.

### B93 — Memory-limit backstop for unlimited workloads — ✅ DONE 2026-07-20
**✅ DONE 2026-07-20.** `k8s/limitranges.yaml` — a `default-memory` LimitRange (default `limits.memory: 2Gi`, `defaultRequest.memory: 128Mi`) in **monitoring · argocd · istio-system · woodpecker · n8n · headlamp**, onboarded via a `limitranges` Argo app in `loose-apps.yaml` (multi-ns pattern, same as `rbac-noautomount`). Memory only — no CPU default (throttling). Explicit limits always win, so the large consumers are untouched; this only catches containers declaring none, including **future** ones.
**Correction to the scope below:** the `musicbrainz` "unlimited container" is `musicbrainz-restore-job.yaml` — a **completed one-off Job** whose manifest already documents *"no resources here on purpose — immutable; Argo can't patch it."* Skipped for the same reason as the superset init-job, so **no explicit-limit work was needed**. kube-system and a blanket data-mesh/weyland LimitRange remain deliberately out of scope.
**Caveat:** LimitRange applies at pod *creation* — existing pods keep no limit until they next restart. Original scope:
**Added 2026-07-18.** kubescape `C-0271` (memory limits missing). **Already largely mitigated**: every large memory consumer (Trino 5Gi, Cassandra 3.5Gi, SonarQube, Neo4j, OpenSearch, DataHub GMS, dagster-user-code, Ray, ClickHouse, Flink, etc.) already carries an explicit limit — the node-OOM risk is handled. Remaining unlimited pods are all small/moderate infra & control-plane (argocd, monitoring sidecars, istiod, woodpecker, n8n, headlamp) + data-mesh musicbrainz + a superset init-job. Low actual risk → this is defense-in-depth + closing the control, not urgent. Scoped approach (do NOT do a blanket 50-workload pass):
- **Per-namespace `LimitRange`** (default `limits.memory: 2Gi`, `defaultRequest.memory: 128Mi`) on the infra namespaces (monitoring, argocd, istio-system, woodpecker, n8n, headlamp) — caps chart/system pods without forking 15 helm-values files, and auto-catches future unlimited pods. 2Gi = containment headroom (all use <500Mi).
- **Explicit limit on `musicbrainz`** (data-mesh), sized from its real working-set.
- **Skip** kube-system (k3s-owned system pods) + the superset init-job (ephemeral) + a blanket data-mesh/weyland LimitRange (heterogeneous — a low default could OOM a future big store).
- CPU limits (`C-0270`) are deliberately NOT set — CPU limits cause throttling; requests-not-limits is the accepted practice.
- Verify with an `OOMKilled` alert (`kube_pod_container_status_last_terminated_reason`) after applying; bump any too-tight limit.

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
- **SEC-1 — ✅ DONE 2026-07-20 (9 of 9).** The sweep found the shared password inline in **9** live places, not the 4 SEC-1 listed. Fixed: `user-code.yaml` ×4 → `secretKeyRef` on a new sealed **`datamesh-store-creds`** (ns `weyland`; secretKeyRef can't cross namespaces) · `cube.yaml` `CUBEJS_SQL_PASSWORD` → sealed into the existing `cube-secret` (re-sealed preserving the live API key) · `mysql.yaml` liveness probe → shell-wrapped reading `$MYSQL_PASSWORD` from `envFrom mysql-secret` (exec probes don't expand `$(VAR)`) · superset `extraSecretEnv.SUPERSET_SECRET_KEY` removed (verified byte-identical to `superset-env`'s copy first — a changed SECRET_KEY orphans every saved DB-connection password) · superset `adminUser.password` removed via `createAdmin: false` (Keycloak OIDC is the real login; break-glass admin already exists). All verified live: dagster/cube/mysql/superset healthy.
  **✅ 9th — superset `connections.db_pass` (EMA-84), fixed 2026-07-20.** The first attempt took Superset down and produced a **wrong** diagnosis, recorded here for a week: that the chart renders `db_pass` into the container's `env:` and *shadows* `superset-env`. It does not. Inspecting the live Deployment showed exactly one explicit env var (`SUPERSET_PORT`); `DB_PASS` reaches all three consumers (`superset`, `superset-worker`, the `superset-init-db` Job) **only** via `envFrom: superset-env`. The outage was the plain cause — placeholdering `db_pass` put the placeholder into the chart-templated Secret (`secret-env.yaml`: `DB_PASS: {{ include "superset.db.password" . }}`).
  `superset-env` is **chart-generated** (`heritage=Helm`, `chart=superset-0.17.2`, Argo-tracked), confirming `seal-secrets.sh` and refuting the values-file comment — so adding a key to it was never viable (wiped on sync). The fix is **precedence, not naming**: an explicit container `env:` entry always outranks the same name from `envFrom`, so `extraEnvRaw` re-defines `DB_PASS` from a new **`superset-db-pass` SealedSecret**, sealed from the live value (no rotation, byte-identical). Verified in chart source that `extraEnvRaw` renders in all three templates (`deployment.yaml`, `deployment-worker.yaml`, `init-job.yaml`) — the Job matters because it runs the Alembic migrations. Argo recreated the immutable Job itself (no manual delete needed); `1 succeeded / 0 failed` + `Synced Healthy` is the real proof of DB auth, since `/health` is shallow and never touches Postgres. Stale `Error` pod from the 07-11 outage reaped.
  **Rotation DECLINED (2026-07-20)** — accepted risk, decided explicitly. The shared dev cred is intentional for a LAN-only lab, the value is already in git history, and rotating would touch every store/secret/runbook/Keycloak for no practical gain here. Relocation-out-of-manifests is the accepted end state; **don't re-propose rotation**. Likewise the ~50 remaining doc hits are **deliberately NOT scrubbed** — they're real operational commands and the DoD requires runbooks carry real commands. Original scope:
- **SEC-1 (2026-07-03)** — Migrate Tier-2 store creds off inline `weyland_dev_password` in
  `k8s/dagster/user-code.yaml` (`TIMESCALEDB_/MYSQL_/MONGO_/CLICKHOUSE_PASSWORD`) → a k8s Secret + `secretKeyRef`,
  and **rotate** the value. Flagged twice by the automated security review. Low-risk on the LAN, but the password
  is committed in git. Do **all four at once** — piecemeal (ClickHouse-only) is inconsistent and gives no real
  benefit while the other three stay inline. Also the ClickHouse `users.d` Secret is already out-of-band (good).

### B94 — Alert on Dagster run failures — ✅ DONE 2026-07-21
**✅ DONE 2026-07-21.** Rewrote `k8s/dagster/freshness.yaml` from a GLOBAL freshness check into a **per-job watchdog** with two independent conditions:
- **`DagsterJobFailed`** — a job's most recent run is `FAILURE` (it ran and broke).
- **`DagsterJobStale`** — a job's last SUCCESS is older than its own cadence budget (~2× the interval, so one missed run doesn't page). Catches "stopped running entirely", which a failure check structurally cannot.

**Root cause of the original blindness:** the old query was `SELECT ... FROM runs WHERE status='SUCCESS'` with **no job filter** — "has ANY run succeeded in the last 90 min?". With timeseries/ai_session/catalog/datahub_emit succeeding constantly, that clock never ages, so a weekly job could fail forever and the watchdog stayed green **by construction**. It wasn't misconfigured; it was incapable. Note the perverse property: an aggregate health check gets LESS sensitive as you add jobs — more green noise to mask any one red.

**`@run_failure_sensor` was NOT used**: the native run-status sensor is broken on this Dagster line (1.13.14, dagster#21526) — the reason the check polls the DB externally in the first place. The mechanism was always fine; only the query was wrong. Revisit on a Dagster major upgrade.

**Verified:** all 10 monitored jobs report SUCCESS with sane ages, 0 alerts (correct — no false positives), and a synthetic alert confirmed the Alertmanager → Telegram path actually delivers.

**Scope decisions:** only SCHEDULED jobs are monitored. On-demand jobs (hydrate/transform/aidlc_kb/`__ASSET_JOB`) and event-driven ones (`lancedb_sync` — its sensor idles for weeks BY DESIGN) are excluded, or idleness would page forever for being correct.

**`weyland_ai_session_schedule` is STOPPED — DELIBERATELY, not a fault.** It was switched off on purpose in an earlier session (the decision was never written down, which is why this audit mis-flagged it as a dead pipeline — twice). Consequence, understood and accepted: the B62 AI-Dev Usage product does not auto-refresh; the Port dashboard reflects the ad-hoc `__ASSET_JOB` materialization from build time, while the rogueone producer keeps mirroring to MinIO for whenever it's turned back on. Correctly left OUT of the watchdog (a deliberately-off schedule must not page). **Revisit deferred — do NOT re-raise as a defect.** If re-enabled: run the job manually first (it has never passed as a job), then add it to `threshold_for()` with a ~6h budget. **Correction:** an earlier reading of this audit flagged `datahub_sensor` as a stopped sensor — it does NOT exist. `DagsterInstance.all_instigator_state()` returns PERSISTED state rows including **orphans** for sensors deleted from code (`datahub_sensor`, `datasets_raw_sensor` — neither is in `definitions.py`; the only live DataHub automation is `datahub_catalog_emit_job_schedule`, RUNNING). Don't treat an entry in that table as proof a sensor is live.

Original scope:
**Added 2026-07-20.** Surfaced by a concrete miss: `weyland_dbt_job` failed **3 consecutive runs** (2026-07-12, 07-19, 07-20) and *nothing told anyone*. Two weeks of the weekly mart build silently not happening; found only because the eval work happened to look at tick history. Dagster is now the spine of the platform (17 jobs, 11 schedules, 2 sensors) — an un-alerted run failure is the single biggest observability hole left after B69.

**The trap that hid it:** a schedule **tick** status is NOT the run's status. A tick reads `SUCCESS` when the daemon successfully *launched* the run — the run it launched can then fail immediately. Any check built on tick status is measuring the wrong thing (this misled the 07-20 investigation).

Scope:
- Alert on run failure → the existing Alertmanager → Telegram path (one pipeline for metrics + logs + this).
- Source options (pick at build time): (a) a Dagster **run-status sensor** (`@run_failure_sensor`) posting to Alertmanager's `/api/v2/alerts` — native, no scraping, catches every job; (b) `dagster-daemon` log-based LogQL alert via the Loki ruler (already wired for B51); (c) scrape Dagster's Prometheus metrics if the deployment exposes run counters.
  (a) is the strongest — a `@run_failure_sensor` is job-agnostic and fires on the *run*, not the tick.
- Include the job name + run URL in the alert so it's actionable from Telegram.
- **Also cover: a job that stops being scheduled at all** (silence ≠ health) — a freshness/heartbeat check per critical job, so "never ran" alarms like "ran and failed".
- Backfill check: audit every job's recent run history once the alert lands, since other jobs may be sitting in the same silent-failure state.

### B95 — Guard against security-hardening collisions (no-automount broke lancedb sync) — ✅ **DONE 2026-08-08.** Class made un-repeatable: `scripts/check-sa-automount-collisions.sh` (static tripwire — fails if any (Cluster)RoleBinding binds a `default` SA; proven trips on a planted collision, green on the real repo) + wired into **DoD Pillar 7** (runs on any SA/RBAC/automount change) + the standing-rule comment already in `rbac-default-sa-noautomount.yaml` + principle in [[k8s-sa-token-vs-rbac-split]]. Scanned clean (0 new high). _(Was 🔴 HIGH.)_
**Added 2026-07-20.** Two individually-correct changes cancelled each other out and the failure was silent for weeks. `lancedb-sync-rbac.yaml` bound its Role to **`weyland/default`**; U10/B69 `rbac-default-sa-noautomount.yaml` then set `automountServiceAccountToken: false` on that same SA. Result: the pod held the RBAC *permissions* with **no token to authenticate with** → `ConfigException: Service token file does not exist` from `config.load_incluster_config()`. Undetected because the op only runs when `lancedb_sync_sensor` fires, and its upstream hydrate jobs are on-demand. Fixed 2026-07-20 with a dedicated `dagster-user-code` SA (`automountServiceAccountToken: true`) + `serviceAccountName` on the Deployment + the RoleBinding subject repointed. See [[k8s-sa-token-vs-rbac-split]].

Scope — make the *class* of mistake hard to repeat:
- **Standing rule, documented in `rbac-default-sa-noautomount.yaml` itself:** before disabling automount on any `default` SA, grep for RoleBindings whose subject is that SA. Each one is proof a pod uses the API (nobody writes a binding otherwise).
- Add that check to the security-hardening section of the DoD, alongside the existing scan-suite gates.
- Consider a scan-suite/kubescape-style repo check: flag any RoleBinding whose subject is a `default` ServiceAccount in a namespace where automount is disabled. Cheap static check, catches the whole class.
- Broader principle worth capturing: **authorization and identity must target the same SA** — changing one without the other fails silently in whichever direction you get it wrong.

### B96 — Eval harness: fixed question set + retrieval-quality baseline — ✅ DONE 2026-07-21
**✅ Golden set shipped 2026-07-21.** `weyland_pipeline/golden_questions.json` (in the package, so the existing `COPY weyland_pipeline/` ships it — no Dockerfile change) + `EVAL_QUESTION_SOURCE=golden|generated` in `eval_testset.py`. Golden mode **ignores `EVAL_TEST_SIZE`** — the file IS the exam; truncating it would silently change the exam between runs and reintroduce the incomparability. Fails loudly if the file is missing rather than falling back to generation (a silent fallback produces a run that LOOKS golden but isn't). Deployed as `weyland-dagster-user-code:v3`.

**20 questions, 10 conceptual + 10 lexical.** Conceptual = run 6's questions verbatim (continuity with history). Lexical = exact-identifier questions (`-Xmx4G`, `readTimeout`, `tempo-prom-metrics`, `ruleSelectorNilUsesHelmValues`, `America/New_York`, `OLLAMA_MAX_LOADED_MODELS`, `31337`, `9092`, `weyland_chunks`, `30500`) — **every token verified present in the indexed corpus first** (ilike over `rag_chunks`), because a question whose answer isn't indexed scores zero for dense AND hybrid alike and proves nothing. Rarer tokens preferred; they discriminate best.

## ⚠️ RUN 7 BASELINE OVERTURNED B74's PREMISE — read this before building hybrid retrieval

Dense-only, golden set, n=180 scores per cell (10q × 6 models × 3 judges):

| metric | conceptual | lexical | delta |
|---|---|---|---|
| context_relevancy | **0.514** | **0.736** | lexical **+0.22** |
| faithfulness | 0.660 | 0.780 | lexical +0.12 |
| answer_relevancy | 0.644 | 0.832 | lexical +0.19 |

**Lexical beats conceptual on every metric.** B74 is premised on "dense embeddings are weak on exact identifiers (config keys, flags, error codes, paths, commands) that BM25 nails" — **this data does not support that.** Dense retrieval handles identifier questions BETTER here.

The weak half is **conceptual retrieval (0.514)**, and BM25 is unlikely to help: BM25 is *also* lexical, so hybrid fusion would reinforce the half that is already strong. Working hypothesis: identifier answers live in ONE distinctive chunk that top-3 retrieval finds, while conceptual questions need synthesis across SEVERAL chunks that `EVAL_ASK_LIMIT=3` never delivers — i.e. the bottleneck is context VOLUME, not sparse-vs-dense ranking.

## ✅ RETRIEVAL-DEPTH EXPERIMENT COMPLETE — three runs, same exam, only `EVAL_ASK_LIMIT` changed

| metric · half | limit 3 (run 7) | limit 5 (run 10) | limit 8 (run 9) |
|---|---|---|---|
| answer_relevancy · conceptual | 0.644 | 0.687 | **0.741** |
| context_relevancy · conceptual | 0.514 | **0.563** | 0.554 |
| faithfulness · conceptual | 0.660 | 0.662 | **0.665** |
| answer_relevancy · lexical | **0.832** | 0.811 | 0.750 |
| context_relevancy · lexical | **0.736** | 0.703 | 0.702 |
| faithfulness · lexical | **0.780** | 0.716 | 0.691 |
| **SUM** | **4.166** | 4.142 | 4.103 |

**Conclusions:**
1. **Depth is a TRADE, not an improvement — and it is roughly LINEAR.** 5 sits between 3 and 8 on nearly every cell; there is no free middle. More context helps CONCEPTUAL synthesis and hurts LEXICAL precision. **Limit 3 wins on aggregate → reverted to 3.**
2. **Dilution is the mechanism.** An identifier answer lives in ONE chunk, so extra chunks are noise. Lexical *faithfulness* declines monotonically with depth (0.780 → 0.716 → 0.691) — the cleanest signal in the data: more plausible-but-wrong material to be unfaithful with.
3. **The wall is RANKING, not volume.** Conceptual `context_relevancy` moved only 0.514 → 0.563 while k nearly TRIPLED. Retrieving more mostly-irrelevant chunks doesn't fix a ranker.

**→ B74 REFRAMED (it survives, on different grounds).** The original premise — "dense embeddings are weak on exact identifiers that BM25 nails" — is **FALSE here**: lexical leads conceptual on every metric at every depth. The real case is **ranking precision in both directions**: get the right chunks into a SMALL top-k rather than widening k. Hybrid/RRF is a precision mechanism; a **reranker** belongs in the same conversation. A third option this data suggests: **per-query-type k** (identifier queries → tight top-3, synthesis queries → more), which is a smarter feature than any constant.

**Caveats:** lexical n = 171/174 vs 180 in runs 9/10 — the `deepseek-coder-v2:16b` 502s all landed in that half (see below). Not enough to flip a 0.09 gap. 10 questions per half is small; treat as a strong signal, not proof.

**Infra findings from the experiment (each cost a debugging round):**
- **tool-server OOMKilled at 2Gi** under `limit=8` → every subsequent `/context/ask` returned **503** and 117/120 results stored that as their error, while the run reported SUCCESS in 1 minute. Raised to **3Gi** (`k8s/weyland-tool-server.yaml`); it then peaked ~2.8Gi and survived. A 503 from an in-mesh service means the POD went away — check `lastState.terminated.reason`, not the caller's logs.
- **502 ≠ 503.** Runs 9/10 produced a handful of **502s with `restarts=0`** — a LIVE pod resetting the connection, not a dead one. Different layer, different fix.
- **Every 502 was `deepseek-coder-v2:16b`**, across two independent runs, late in the matrix. Model-specific, not ambient flakiness — worth isolating.
- **Both eval stages now FAIL LOUDLY** (>10% error rate raises) and **log errors + progress**. Previously `except: failed += 1; continue` swallowed everything: a run where 351/360 judge calls were skipped reported green. Progress logging (per-model timing, every-5-cells) ships with `:v6` — a 21-minute job that logs nothing is indistinguishable from a hang.

**Caveats:** judges may favour crisp factual answers over synthesis; 10 questions per half is small. Treat as a strong signal, not proof.

**Method note worth keeping:** this is exactly why the instrument was built BEFORE the feature. Building B74 first would have shipped a change against a false premise, produced a flat lexical half that was already at 0.74, and left nobody able to explain why.

Original scope:
**Added 2026-07-20**, out of the first eval runs since B79 moved Ollama to rogueone (runs 5 + 6 both green end-to-end, so the Sat 03:00/05:00 schedules are proven).

**Finding 1 — the leaderboard is NOT comparable across runs.** `eval_testset` generates a FRESH set of 10 questions per run (`eval_questions.run_id`), so run N's absolute scores are measured against a different exam than run N-1's. Cross-run deltas therefore mostly measure question difficulty, not model or system quality. Only the **within-run ranking** is meaningful today. This confounded the 07-20 investigation: run 5 scored ~0.30 below runs 3/4 across *all six models at once*, which reads exactly like a system regression and isn't.
- Fix: an OPTIONAL **fixed/golden question set** (pin a run's questions, or a curated set in git) so cross-run tracking measures the *system*. Keep per-run generation as a mode — it guards against overfitting to a static exam. This is a prerequisite for B84 (productizing the eval as a data product): a leaderboard you can't compare over time isn't a product.

**Finding 2 — `context_relevancy` looks genuinely low, and it's the RETRIEVAL metric.** Runs 5 and 6 (two INDEPENDENT question sets) both land at **0.41–0.60**, versus **0.71–0.89** in runs 3/4. Two independent samples agreeing is weak-but-real evidence this isn't only question drift. Worth an investigation, and it gives **B74 (hybrid BM25 + dense retrieval)** something it never had: a measurable before/after baseline. Validate B74 against `context_relevancy` on a fixed question set.

**Finding 3 — the recorded "gpt-oss:20b is the defensible pick" (B4) no longer reproduces.** In run 6 `gpt-oss:20b` is near-bottom on all three metrics while **`qwen3-coder:30b`** is first or joint-first on all three. Two runs now disagree with the original call. Re-establish the pick on a fixed question set before treating either as settled.

**Operational note:** rogueone has ONE 16 GB GPU driving both the desktop and Ollama, and no usable iGPU. Ollama guardrails (`nodes/rogueone/systemd/ollama-gpu-guardrails.conf`) are **validated under desktop contention**; BIOS → Hybrid Graphics is deferred.


### B97 — n8n encryption key committed to the PUBLIC repo — ✅ DONE 2026-07-22 (untracked; rotation DECLINED; guard built)
**Raised properly 2026-07-20** (known since 2026-06-15, buried in a B-audit status note and never actioned — 5 weeks).

`nodes/mother/lab/weyland-platform/k8s/n8n/encryption-key.txt` is **tracked in git** (65 bytes = a 64-char hex key + newline) in the **PUBLIC** `edtbl76/weyland-lab`. It is `.gitignore`d (lines 101-103) — but **.gitignore does not untrack an already-tracked file**, which is exactly why the note was written and the risk never actually went away. Verified still tracked 2026-07-20.

**What it protects:** `N8N_ENCRYPTION_KEY` encrypts n8n's stored credentials. n8n holds exactly **1 credential — `sshPrivateKey | SSH Weyland Lab`** — i.e. the protected asset is an **SSH private key**, the highest-value credential type in the lab.

**Actual exposure:** the key alone is useless without n8n's Postgres DB, which is LAN-only. An attacker needs BOTH halves. So this is not "the SSH key is public" — it is "one half is public, permanently, and cannot be unpublished."

**Why the SEC-1 sweep missed it:** that pass hunted the shared dev-password *string*. A high-entropy key in a bare `.txt` matches no password pattern, and gitleaks doesn't flag a context-free hex blob. Same class as the B95 SA/RBAC collision — each control correct, the gap between them.

Scope:
- **Untrack** the file (gitignore alone is insufficient — it must leave the index). Removing it does NOT unpublish it; history keeps it.
- ~~Rotate `N8N_ENCRYPTION_KEY`~~ — **ROTATION DECLINED 2026-07-21, accepted risk, decided explicitly. Do NOT re-propose.** Same posture as the shared dev password: LAN-only lab, and the other half (n8n's Postgres) never leaves the network, so the published key is not independently usable. Consequence accepted knowingly: untracking does NOT unpublish it, so the key stays in history and the `SSH Weyland Lab` private key it protects is treated as compromised-but-accepted.
- If that ever stops being acceptable (n8n exposed beyond the LAN, or its DB leaves the network), rotation is cheap here — exactly ONE credential to re-enter — and the new key should be stored as a **SealedSecret**, never a file in the tree.
- History rewrite: **NOT recommended** — disruptive on a public repo, and the key must be assumed compromised regardless. Rotation is the real revocation.
- ✅ **Follow-up guard BUILT 2026-07-22** — but the real gap wasn't "no entropy check", it was that **gitleaks `dir` honors `.gitignore`**, so a file that is tracked AND gitignored (a secret someone hid after committing it — exactly the n8n case) is invisible to it. New `secret_files()` check in `services/scan-suite/scan.py` finds that intersection directly via `git check-ignore --no-index` over the tracked-file list — no entropy heuristics (which would flood on the accepted dev password + sealed ciphertext). Verified against the live repo: flags **exactly 1 file** (the n8n key), zero false positives; marked CRITICAL (precise → trustworthy, unlike osv's phantom highs). Ships as `scan-suite:v2`. It will keep flagging the n8n key on every weekly run **until the untrack above is done** — a persistent nag that closes the loop.

### B98 — Node-level OOM / memory-pressure alerting — ✅ DONE 2026-07-22
**Added 2026-07-22.** A single pod's memory storm OOM-exhausted mother's **entire 64 GB node** — the OOM-killer took down trino/mlflow/tempo/the network stack, the node went unreachable (rogueone got `no route to host`), and **NOTHING paged.** We have node-**disk** alerts (B69) and Dagster-run-failure alerts (B94), but the one failure mode that takes the whole platform down — a pod eating all node RAM — has no alarm.
- **Add:** `KubePodOOMKilling` (fires on any container OOMKilled — often shipped-but-disabled in kube-prometheus-stack; enable or add it) + a **node memory-pressure** alert (`node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.10` for 5m) → Alertmanager → Telegram. Pair `up==0` with `absent()` per the LGTM pattern.
- **Why it matters here specifically:** mother is a single k3s node — there's no other node to reschedule onto, so a node-RAM exhaustion is a total outage, not a degraded one. This is the highest-value missing alert on the platform.
- Same class as B94: a control that was silent on the exact failure it should catch.

### B99 — 2026-07-21 outage: SWAP-induced thrash → control-plane/NETWORK loss on the single node
**Root-caused AND fix-verified 2026-07-22 by a live A/B test (after three wrong turns — see below).** The actual outage was **NOT an OOM cascade, NOT the mlflow storm, and NOT (primarily) a missing kubelet guardrail.** It was **swap.**

**What actually happened (2026-07-21):** mother dropped off the LAN — rogueone got "no route to host". The real chain: **node memory pressure → the kernel SWAP-THRASHED** (swapping out idle apiserver / `systemd-networkd` / `systemd-resolved` pages instead of cleanly killing the offender) **→ those daemons stalled on swap-in → control plane + network stack unresponsive → mother unreachable.** Memory event → thrash → NETWORK loss.

**ROOT CAUSE — swap was enabled on a memory-overcommitted single-node k8s box.** mother had a 4Gi swap active (`free -m` showed 1.1Gi already swapped at rest). Kubernetes assumes swap **off**: with swap on, memory pressure produces thrashing (slow, node-killing) instead of a fast, recoverable OOM. Pod memory *limits* sum to ~300% of the 64Gi, so pressure is routine — and swap turned every pressure spike into a control-plane stall.

**PROVEN by A/B test (2026-07-22), same BestEffort memory-hog pod both runs:**
- **Swap ON** → hog grew, apiserver returned `TLS handshake timeout` on `127.0.0.1:6443`, node went `NotReady` — **reproduced the outage** at moderate pressure.
- **Swap OFF** (`swapoff -a`) → hog grew to **603Mi available** (extreme pressure), then the **kernel OOM-killer** cleanly killed the BestEffort hog (`OOMKilled`, exit 137, ~14Gi reclaimed instantly); **kubectl stayed responsive and the node stayed `Ready` the entire time.** Node survived far worse pressure than swap-on died at.

**THE FIX:** **disable swap** (`swapoff -a` now; permanent via fstab — codified in `nodes/mother/host/…`). With swap off, memory pressure → fast kernel-OOM of the biggest offender (BestEffort/high-`oom_score` first, never a critical pod) → node recovers on its own.

**Backstop (kept, NOT the fix):** kubelet reserves in `nodes/mother/host/rancher/k3s/config.yaml` (`system-reserved=2Gi` + `kube-reserved=1Gi` + `eviction-hard=memory.available<1.5Gi`). The A/B test showed these did **not** fire — a fast runaway outran the ~10s eviction poll and the **kernel OOM-killer** is what actually caught it. On a single node that's the correct last line; the reserves remain as documented defense-in-depth and shrink the overcommit. **B98** alerts on node-memory pressure regardless.

**Three wrong turns, recorded so the forensic lesson sticks:** (1) diagnosed the **mlflow Huey job runner** storm (197 python3.10 kills) as the incident — real but **Jul 14-16**, contained to mlflow's 4Gi cgroup, self-resolved by Jul 17; not the outage. (2) "fixed" it by DISABLING the runner — WRONG, demos require it; reverted. (3) diagnosed a missing **kubelet memory guardrail** as the structural cause and shipped reserves/`eviction-hard` as "THE FIX" — the A/B test disproved it: those knobs never fired; **swap** was the cause and **swap-off** is the fix. Lesson: don't declare a fix without a repro — the test both found the real cause and demoted two plausible-but-wrong ones.

**Secondary hygiene (kept, complementary — NOT the outage fix):** mlflow `limits.memory` 4Gi→8Gi (room for the Huey job runner the demos need; the runner STAYS ON) + Tempo 2Gi→3Gi (it OOM-looped at 2Gi under peak trace load). Safe now that swap is off (pressure resolves as fast contained OOM, not thrash).

Original notes:

**The python3.10 storm = MLflow's server-side JOB RUNNER.** The 2.18→3.14 upgrade (B47) silently added a Huey-based
job subsystem (`mlflow.server.jobs`) that spawns ~7 `huey_consumer` processes, each `-w 5/10` workers — UNBOUNDED,
unsized to the pod. `--workers 1` bounds only the WEB server (1 uvicorn proc); zero effect on this. At idle ~9
python3.10 / ~1.3Gi; under job load the pool balloons past the 4Gi cgroup → `memory.oom.group` kills all 9 at once
→ respawn → storm (197 python3.10 kills in the boot). **Fix — HEADROOM, runner stays ON (the job runner is REQUIRED: demos + use-cases depend on it).** It is a *used*
feature that lacked memory, not an inert one to disable. **Applied: raised mlflow `limits.memory` 4Gi → 8Gi**
(`k8s/mlflow/mlflow.yaml`; request 512Mi→1Gi) — room for the web server + the 7 huey consumers + in-flight jobs so
the cgroup no longer OOMs. Only the limit moves (no scheduling reservation); node has ~14Gi physical free. Revisit
if a single heavy job still OOMs at 8Gi (then raise again, or investigate a specific job). ⚠️ An earlier attempt
DISABLED the runner (`MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false`) on a wrong "it's inert" assumption — REVERTED;
that would have broken the demos. Recurrence is alarmed by B98.

**Forensic lessons (cost several wrong turns):** (1) `oom_memcg` counts mis-named the culprit as `tempo-0` — that
was tempo OOM-looping SEPARATELY at its own 2Gi limit (collateral). The storm's real home is in the OOM-report
BODY: the `Tasks state` list + `oom_memcg=.../pod<UID>.slice` + `memory.oom.group set`. (2) `grep oom-kill: | task=`
misses kills that only emit the `Memory cgroup out of memory: Killed process` line. See [[node-oom-forensics]].

**Tempo:** OOM'd 72× at its 2Gi ceiling under peak trace load (eval mesh traffic + LGTM self-monitoring, both up
2026-07-21). Raised **2Gi→3Gi** (`k8s/tempo/tempo-values.yaml`); baseline is ~326Mi so this is peak headroom.
Revisit with sampling if it recurs.

Recurrence is now ALARMED by B98 (KubePodOOMKilled + node-memory pressure). Original notes:
**Added 2026-07-22.** Two threads from the node-OOM incident, both needing fresh investigation:
- **The python3.10 storm.** The console showed hundreds of `python3.10` processes (UID:0, ~150 MB each, `oom_score_adj:993`) spawned in ~70 s — a fork-storm that ate tens of GB. The memcg forensic attributed 71 OOM events to **`monitoring/tempo-0`'s** pod cgroup, but **Tempo is a Go binary running as UID:10001** — the python3.10/UID:0 identity does NOT cleanly match tempo. So either the memcg accounting is rolling up a parent cgroup, or there's a secondary spawner. **Unresolved — needs a live repro with better forensics** (`journalctl -k` full OOM report incl. `task_memcg` + `task`, per-cgroup memory.current sampling). Do NOT assume tempo is the python3.10 source.
- **Tempo sizing.** tempo-0 (limit 2 GB, baseline ~326 MB) **crash-looped 71× at its 2 GB ceiling** under last boot's peak trace load (eval mesh traffic + the new LGTM self-monitoring, both added 2026-07-21). Fine at baseline, too tight at peak. Either raise the limit, tune retention/compaction (`max_block_bytes`, ingester flush), or cap trace ingestion. Feeds B98 (a right-sized Tempo won't OOM-loop; the alert catches it if it does).

---

### B128 — Wire rogueone DCGM GPU telemetry → Prometheus/Grafana (dcgm-exporter) — 🟡 MEDIUM (2026-08-15)

rogueone already runs `dcgm.nv-hostengine` (the NVIDIA DCGM host engine — active, continuously polling the RTX 5000 Ada), but `dcgm.dcgm-exporter` is **disabled**, so the GPU telemetry it collects is consumed by nothing. Enable the exporter and scrape it into the existing weyland LGTM stack (Prometheus/Grafana) to get per-GPU **utilization, VRAM used, temperature/throttle state, power draw, clocks**, and — most valuable — **Xid error counts** (GPU-fault codes). rogueone is the lab's GPU training box (Ray + MLflow + genre-trainer), so this gives real observability for training runs (spot thermal throttling, VRAM pressure, under-utilization) and **early warning of GPU faults** — e.g. the `NVRM Xid 16` (display-engine) events that showed up in the freeze forensics would surface in Grafana instead of only post-mortem in `dmesg`. Effort: `snap start --enable dcgm.dcgm-exporter`, add a Prometheus scrape target for the exporter's `:9400/metrics` (LAN NodePort or direct), import the standard NVIDIA DCGM Grafana dashboard. Decided keep-over-remove during the 2026-08-15 rogueone cleanup (it's harmless running and genuinely useful once wired). See [[remote-training-rogueone]], [[observability-otel-b49]].

---

### B129 — Catalog installed tools/packages per machine in Port.io — 🟢 LOW (2026-08-15)

Build a living inventory of software installed across the lab machines (rogueone, mother, weyland) in **Port.io** — snaps, flatpaks, apt packages, pip/npm global tools, container images — as blueprint + entities, with per-machine ownership, keep/remove status, and a one-line rationale each. Goal: replace ad-hoc "what's installed and why" audits with a queryable catalog we can diff over time. Ties into the existing `quality-tools.yaml` SoT pattern (extend or complement it). Seeded by the **2026-08-15 rogueone snap/package audit** — decisions so far, to be codified as the first entities:

**rogueone — KEEP (with rationale):**
- `canonical-livepatch` — live kernel-CVE patching; valued, and it has applied 0 patches so far (no wildcard today).
- `dcgm` (`nv-hostengine`) — GPU telemetry; harmless + useful once wired to Grafana (see B128).
- `cups` + `cups-browsed` — prints regularly; snap is current so the 2024 CUPS CVEs are patched.
- `steam` — occasional gaming (caveat: don't run games during GPU training — VRAM contention).
- `scummvm`, `dosbox-x` — retro gaming, actively used.
- `altair` — GraphQL client; occasional use, redundant-ish with Postman but low cost to keep.
- `appimage2deb` — AppImage→deb utility; used when installing software.

**rogueone — REMOVED (2026-08-15):**
- `deepseek-desktop`, `gemini-desktop` — AI-chat Electron wrappers, leftover trials (full local AI stack already covers this).
- `ms-365-electron` — unofficial M365 web wrapper, redundant with a browser.
- `curl` (snap) — redundant with, and more-confined than, system `/usr/bin/curl`.

**rogueone — REMOVED (2026-08-15, full triage complete):**
- Snaps: `brave` (unused, never launched), `dbeaver-ce` (idle since Mar; DataGrip covers DB), `flutter`, `fx` (jq/Postman cover it), `julia`, `jupyterlab-desktop` (Anaconda covers), `data-science-stack` (redundant w/ weyland + native CUDA), `kontena-lens` (kubectl + JetBrains + ArgoCD cover), `pieces-for-developers` + `pieces-os` (redundant w/ AI stack). _(Plus earlier: deepseek-desktop, gemini-desktop, ms-365-electron, curl.)_
- Flatpaks: `org.gnome.DejaDup` (dormant, wrong-fit → B130), `org.telegram.desktop` (web client), `org.x.Warpinator` (rsync covers LAN).
- apt: `duplicati` (2nd dormant backup → B130), `timeshift`, `warp-terminal`, `thunderbird`, `webex`, `sqlitebrowser` (DataGrip covers SQLite), `stacer` (CLI covers).

**rogueone — additional KEEP notes:** kept `docker-desktop` (retired/unused but removal drags docker libs — not worth the cascade), `clamtk` + full `clamav` stack (only AV on the box; `freshclam` disabled → defs stale), plus the standard dev/CLI toolchain. Full KEEP/REMOVED inventory in **Linear EMA-188** (comment) and `/home/edwardmangini/rogueone-snap-cleanup.md`.

_Audit COMPLETE for rogueone 2026-08-15 (snap + flatpak + apt). mother + weyland still to inventory. Linear: EMA-188._

---

### B130 — Proper backups on rogueone (restic → MinIO) — ✅ **DONE 2026-08-20 [Linear EMA-189]**

**Shipped:** encrypted, deduplicated, incremental **restic → MinIO** (`s3:…:30990/rogueone-backup`, ~415M deduped), daily **02:30 NY** systemd **user** timer (`enable-linger`), restore-tested. Config git-tracked under `nodes/rogueone/{backup,systemd}`; secrets in the central gitignored `scripts/.env` (sourced). **Scope = the "local-only gap"** — the 3-domain model: code→GitHub, media→Google Drive, **everything-else→restic**. Backs up dotfiles + `~/.config` (curated) + `~/.claude` memory + secrets (`~/.ssh`/`~/.gnupg`/GNOME-keyring/**mkcert root CA**) + curated `~/Documents` + each **allow-listed** git repo's `git ls-files --others` (untracked WIP + gitignored `.env`/local data) **minus reproducible bulk**. **Reporting (both):** Port `backup` blueprint + **weyland Backups** dashboard (see) **and** an Uptime-Kuma **push heartbeat → Telegram** dead-man's-switch (alert). During scoping, the big media (GuitarBooksAndTab courses, music **Stems**) was moved into Google Drive so restic excludes it. **Hard-won gotchas:** (1) restic does **NOT** apply `--exclude` to a path handed to it explicitly via `--files-from` (it honours an explicit target) → the repo bulk (`node_modules`/`.next`/`__pycache__`/Gradle `caches`) must be filtered **in the script** before restic sees it — a first run ballooned to 5.1G before this; (2) `restic forget` defaults to `--group-by host,paths`, so a drifting path-set retains a separate lineage → use `--group-by host`; (3) `kuma.weyland.lab/api/push` sits behind `traefik-forward-auth` (307→Keycloak) → added a `/api/push`-only Ingress **without** the middleware (the push token is its own auth). Docs: [runbooks/backups.md](runbooks/backups.md) · [diagrams/flow-backup.md](diagrams/flow-backup.md) · [demos/backup-restore.md](demos/backup-restore.md) · `nodes/rogueone/backup/README.md`. **Original context (2026-08-15):**

rogueone effectively has **no active backups**: both installed backup tools were dormant — Déjà Dup last ran May 2025 (Google-Drive/pop-os-era config) and `duplicati` was a second unused one; both removed in the B129 audit. Replace with **restic targeting the existing MinIO (S3)** — encrypted, deduplicated, incremental, cron/systemd-timer driven — the idiomatic $0 lab choice that reuses infra we already run (vs a desktop GUI → Google Drive). Scope tightly: code is already in git, and the STUD.io masterdb already backs up nightly to MinIO, so the real target is **dotfiles/config + local non-git data** (scratch work, local models/datasets not reproducible from the cluster). Acceptance: dedicated MinIO bucket + encrypted restic repo; backup script with sensible excludes (`~/.cache`, venvs, model blobs already in MinIO); scheduled with keep-daily/weekly/monthly prune; a **restore test** (a backup you haven't restored isn't a backup); creds via the gitignored `.env` convention. Surfaced during the B129 rogueone cleanup. Linear: EMA-189. See [[data-mesh-b1.2-storage]] (MinIO), [[feedback-local-dotenv-convention]].

---

### B131 — Open-PR lifecycle: surface AND resolve dependency + CI PRs — ✅ **DONE (2026-08-23)**

**Shipped: `pr-staleness-check`** (`k8s/pr-lifecycle/pr-staleness.yaml`) — a daily 05:45 NY CronJob that lists open PRs across the **six active repos** via the GitHub API, applies a per-kind age budget, and POSTs a synthetic alert to the **Alertmanager v2** API. No routing change was needed: the top-level route is a catch-all to `telegram`.

**Two budgets, because the two kinds of PR mean different things when they sit.** A `ci/image-bump-*` PR older than **1 day** means the ship loop stalled — the B135 failure this exists to catch, and a day is already generous for a machine-authored PR whose only job is to be merged. Anything else is a human's work in progress and gets **7 days**. Keyed on the **branch prefix**, not the author: the prefix says what the PR *is*, the author only says who pushed the button, and the anchored glob means `feature/ci-image-bump-lookalike` does not qualify.

**Daily, not `*/30`.** Synthetic alerts carry no `endsAt`, so Alertmanager auto-resolves after `resolve_timeout` (5m) and treats each firing as a NEW alert — meaning the CronJob cadence **is** the Telegram rate. At `*/30` a single stale PR would send ~48 messages a day, which is not nagging, it is training the operator to ignore the channel. It would also have violated `schedules.md` Design Rule #5 (no mid-day auto-runs).

**The watchdog's own first live run found the bug this whole effort is about.** `curl -sf … | jq` collapsed every non-2xx to exit 0, so a 404 on a private repo reached `jq` as empty input and the run reported "4 open PRs checked" — indistinguishable from a genuinely clean sweep, while silently watching **one repo of six**. Now `curl` writes the body to a file and the status to stdout so the two are never conflated; every repo is attempted even after one fails; and the run exits non-zero naming what it could not check. **A watchdog that goes quiet when it cannot see is worse than no watchdog, because it emits a green signal.**

**Decision logic lives in a ConfigMap**, not inline in container args, because `scripts/tests/pr-staleness.bats` extracts and executes that exact text — a tested copy beside a deployed copy drifts, and the drift is silent because both halves keep passing their own checks. The suite's first test asserts the logic is actually extractable; without that tripwire every later test would be vacuously green against an empty file.

**Live evidence:** three Job runs 2026-08-22. Run 1 failed correctly (`GITHUB_TOKEN not set` — the Secret held an empty value, caught by verifying the stored `b64len` rather than trusting `DATA 1`). Run 2 hit a 404 on `startme-curator` and **named it, attempted all six, exited non-zero**. Run 3: six repos fetched, **4 real alerts** delivered to Telegram and visible in Alertmanager.

**Companion shipped under B135:** `cron-freshness-check` — same pattern pointed at the Woodpecker API, because the *other* way the loop stalls is the nightly cron dying, and a Woodpecker cron is not a Kubernetes object so no metric can ever see it.

**Shipped:** `k8s/pr-lifecycle/pr-staleness.yaml` · `scripts/tests/pr-staleness.bats` (7 tests) · sealed `pr-lifecycle-github` · `runbooks/pr-lifecycle.md` · `schedules.md` row · `diagrams/flow-ship-loop.md` § Watchdogs.

**Residual:** the six repos this watches diverge from the six the Port `github-weyland` integration maps (this set carries `startme-curator`, Port carries `midi_real_book`) — real, deliberate, and tracked in **B138** (repo coverage parity); do not silently reconcile one to the other. Port PR ingestion itself was completed 2026-08-23 and folded into **B137**.

Linear: EMA-192.

Give Dependabot dependency-update PRs a durable, queryable home instead of ad-hoc GitHub browsing. **Quick / ad-hoc (gh):** `gh pr list --repo edtbl76/weyland-lab --author "app/dependabot" --state open` (across repos: `gh search prs --author app/dependabot --state open --owner edtbl76`). **Durable answer = Port** (the lab IDP): its GitHub integration can ingest `pull_request` entities, so build a dashboard table/scorecard filtered to `author = dependabot[bot]` (e.g. "open dependency PRs > N days") — same "see" layer as everything else; first check whether the current GitHub integration mapping already ingests PRs, else it's a mapping addition. Composes with **B63** (CI signals → Port). **Prerequisite:** Dependabot must be enabled per repo (a `.github/dependabot.yml`) for the PRs to exist. **LAN caveat:** Dependabot PRs will NOT auto-trigger Woodpecker CI — GitHub can't reach `woodpecker.weyland.lab` for webhooks (the same wall as all LAN CI); running CI *on* them would be a poll/cron extension of the B57a nightly cron (enumerate open PRs → run the pipeline per branch) — tracking ≠ running. Acceptance: a one-glance view of open Dependabot PRs (age / repo / target dep) — a `gh` alias at minimum, a Port dashboard widget if durable visibility is wanted. $0 (native GitHub + Port). Linear: EMA-192. See [[port-catalog-docs-b59]].

**WIDENED 2026-08-20 — from tracking to resolution, and from Dependabot to every open PR.** The original scope stopped at visibility ("tracking ≠ running"), which left the actual PRs unowned. That gap bit on 2026-08-20: **CI image-bump PR #12 sat open and unnoticed for a day**, so the whole 11-image fleet ran two builds behind while every surface reported green — the pipeline goes green at "opened a PR", and `notify-port` reports the *pipeline* outcome, never whether the PR was merged. A successful build and an undeployed image are indistinguishable from everything we watch. Dependabot PRs rot the same way for the same reason, so the item now covers **any open PR**, not just `dependabot[bot]`.

**Current backlog of rot (2026-08-20):** `#7` gitpython 3.1.52 → 3.1.58 (**12 days**), `#8` sqlparse 0.5.5 → 0.6.0 (**3 days**), both in `services/genre-trainer`. Worth doing rather than tidying: the same day's scan reported **osv-scanner 74 high / pip-audit 55 high**, and some of those are very likely these exact dependencies — merging them should move the scan numbers, which is the check that they mattered.

**Added acceptance:** (a) an **age-threshold alert** (open PR > N days → Telegram, same path as the other alerts) so a forgotten PR announces itself instead of waiting to be noticed — this is the DoD §6 "Triggered" pillar applied to the git seam; (b) a **routine for resolving** them, not just seeing them — review, merge or close-with-reason, so "open" always means "someone still has to decide"; (c) **superseded-PR handling** — when the image CI opens a newer bump, the older one must be closed, since merging it after the newer one **rolls images backwards** (exactly the #12-after-#13 trap). Relates B63 (CI signals → Port), B57a (the image CI that opens these), B134 (the other class of silent failure found the same day).

---

### B132 — start.me Curator: classify new bookmarks at save time — 🟡 MEDIUM (2026-08-18)

**Full design: `aidlc-docs/b132-startme-curator-design.md`.** Chrome MV3 extension that files a new bookmark into the right start.me widget **at save time**, against the 1,968-link / 147-widget taxonomy rebuilt 2026-08-05 → 08-08 (2,214 → 1,968 links; 85 → 147 widgets; `Misc.` 195 → **0**; descriptions 16% → **100%**). **The problem is entropy at the edges:** every new link is a decision against 147 widgets, and the cost of deciding is high enough that links get parked instead of filed — parking is precisely what produced `Misc.` the first time. The vendor Bookmarker extension makes it worse: it saves to a start.me **inbox**, i.e. a `Misc.` that fills itself. Requirement (operator-stated): the decision happens at save time and the item is **done** — no queue, no second pass.

**KEY FINDING — start.me has an undocumented write API.** The earlier "no write API" conclusion was **wrong**; it held only for the *public* API. The vendor extension (`obgopghdefjihikoknnjfooahlleabno` v7.3.0) ships a full private client, readable from its on-disk JS. Auth is **cookie-only** (`credentials: "include"` — no CSRF, no bearer, no signature). **Verified live 2026-08-18:** `GET /pages/tree_extension.json` (page→widget tree **with IDs**, 200) and `GET /tools/check_link_exists?url=` (200) — the latter returns the *existing item* rather than a boolean, including `status_code` + `broken`, which means **start.me health-checks links server-side** (a free replacement for `deadcheck.py` and a standing answer to "what rotted"). **WRITE PATH VERIFIED 2026-08-22** — spike created a widget (`POST /page/{pageId}/widget` → **201**) and a bookmark in it (`POST /widget/{widgetId}/item` → **201**) on Weyland Lab, then read both back from the tree. Feasibility is settled. **Three schema findings:** (a) **`item_id` and `link_id` are distinct** — the *link* is the URL entity (url/title/description), the *item* is its placement in a widget (index, folder); one link carries many items across widgets, which is why `check_link_exists` returns an array — **the DB must mirror this split**, and `final_taxonomy.json` being flat cannot represent multi-homing; (b) **`folder_id` is live in the data model** — the *group* layer abandoned during the rebuild, currently null everywhere: keep the column, don't design around it yet; (c) **creation returns 201, not 200**, and the vendor client checks `if (200 != status) reject` — **their own extension treats a successful create as a failure**, so assume its status handling is unreliable and accept 201. Still source-only: `POST /widget/{widgetId}/items` (batch), `PATCH /users/unsorted_link/{id}`, `GET /tools/title?url=`. Reconciliation against the live account: **147/147 widgets match `final_taxonomy.json`, zero unmatched.**

**Design:** click (or `Alt+B`) → URL/title/`<meta description>` → parallel dupe-check + cached tree → target list = `urllist` widgets on `is_archived === false` pages, Weyland Lab excluded → one Haiku call → top 3 + confidence → popup with **editable title + description** → `POST /widget/{id}/item`. Descriptions are non-optional: start.me cross-page search covers title + URL + description, so descriptions **are** the retrieval surface, and save time is the only moment one ever gets written. The classifier prompt carries the three locked taxonomy rules **verbatim** (subject-beats-medium · split-papers-from-tools · name-by-the-reach-for-moment) — without them a model reverts to filing by content type, the exact failure the rebuild corrected. Low confidence offers **Create new widget**, never a catch-all; **no `Misc.` may ever be created**. Catalog keys on **widget ID, never name** — two page names drifted within days of import (`Personal and Accounts` → `Personal & Accounts`, `Security & Identity` → `Security and Identity`).

**DIRECTION — database + application (2026-08-18).** The extension is a **client, not the product**. The 1,968-link corpus is the asset; start.me is one rendering of it. The taxonomy moves into a **database** with an application built around it — the original 2026-08-05 intent ("start.me becomes generated output, not the master copy"), deferred then because no write path existed; the write API removes that blocker. **Why a DB and not a file:** `final_taxonomy.json` currently lives unversioned and unbacked in `~/Downloads/` (one `rm` from gone), and it **cannot live in this repo — `weyland-lab` is public** and the corpus includes personal-account links (health, education, finance, memberships); a lab-internal datastore is the correct home, a public repo never is. It also makes structure + links queryable together — "what rotted", "what's over 45", "what has no description" stop being one-off Python scripts. **DATASTORE — SQLite, decided 2026-08-22.** Postgres was the first instinct and was **wrong** — reached for because the lab already runs it, not because the requirements asked. The corpus is **1,968 rows (~825KB), single-writer**; multi-writer safety/pooling/scale all go unused, and the cost is a server + credentials + a NodePort hop. SQLite wins on requirements *and* on the goal: one file (backup = copy, versioning = commit — the `~/Downloads/` risk dies outright); no server/creds/NodePort; **FTS5** for full-text over title+description (the same surface start.me's own cross-page search uses); **`sqlite-vec`** preserves the embedding-prefilter argument that pgvector was carrying; **runs in-browser via WASM** so the extension needs no backend; and **shareable** — `datasette publish` turns the file into a browsable/queryable site with a JSON API, with a subset export being a `WHERE` clause (tech pages yes, `Personal & Accounts` no). Gives up the free nightly `postgres-backup` CronJob — but a single file is the easiest possible thing to feed restic → MinIO (**B130**). **Code + corpus live in `edtbl76/startme-curator` (private)** — this repo is public, the corpus carries personal-account links, and the private-API client shouldn't be published either. Dupe-check / tree-fetch / classify / POST all become the **application's API surface**, with the Chrome extension a thin caller and start.me sync a job rather than the point. **WORKING ASSUMPTION (a) — DB is truth, start.me is the UI** (operator 2026-08-18: *"I assume the DB will be the source of truth and the page will be the 'UI'"*) — recorded as an assumption, **not locked**; it doesn't gate the write spike. Alternatives kept for the record: (b) **replaced** — the app grows its own UI, no vendor risk, most work, rebuilds a UI that already exists; (c) **sidecar** — start.me stays authoritative, DB only powers classification + reporting, least work but the corpus stays hostage to a private API. **OPEN EDGE — the operator edits in the UI:** two pages were renamed directly in start.me within days of import, so naive one-way sync would destroy those edits. (a) therefore needs a rule for UI-originated structure changes — either **reconcile-first** (each sync pulls the live tree, diffs it, adopts renames/new widgets/reorders into the DB before pushing links; safe because the tree carries stable **widget IDs**, so a rename is an ID whose title changed, not a new widget) or **split ownership** (start.me owns structure, DB owns links — simpler and matches how the operator actually works, at the cost of the DB not being able to restructure). Reconcile-first is the better fit and is cheap given stable IDs. **Decide before the first sync job, not before the spike.**

**Build order:** (0) **decide the start.me role** (a/b/c above); (1) ~~write-path spike~~ **✅ DONE 2026-08-22** (widget + item created on Weyland Lab and read back, 201/201 — gate lifted); (2) ~~schema + ingest~~ **✅ DONE 2026-08-22** — `edtbl76/startme-curator` (private): SQLite, `link`/`item` split, `curated_*` views scoping to the 14 pages, FTS5 over title+description, **11 invariant tests** encoding what the rebuild bought; 1,968 links / 147 widgets / 14 pages ingested, zero unresolved. **Bug the tests caught:** page titles are *not unique* — `Business` and `Music & Studio` each exist twice (live + archived) — so resolving placement by title let an archived widget shadow the live one it shared a name with, silently filing 8 links onto a retired page; the original round-trip test compared titles too and was blind to it. Fixed, with a regression test asserting nothing lands off-scope. **Restates the rule: key on IDs, never titles.** (3) extension skeleton **with no AI** (tree fetch + `urllist` filter + searchable picker + manual save) — shippable alone, already beats the vendor extension; (4) ~~classifier~~ **✅ DONE 2026-08-22** — top 3 + one-line reasons, manual picker retained underneath, degrades to the picker on any failure so filing never depends on ranking; low confidence offers a *named* widget and refuses `Misc.`. Uses a **forced strict tool call** (not `output_config.format`) — note strict schemas accept only a JSON Schema *subset* (`type`/`properties`/`required`/`additionalProperties`/`items`/`description`/`enum`), and `minItems`/`maxItems` **400s the whole request** rather than being ignored; a test now asserts the keyword set. Model defaults to `claude-opus-5`, overridable from storage. **Recommendation quality not yet assessed.** (5) optional health sweep across all 1,968 via `check_link_exists`. Step 2 standing alone is the hedge if the classifier disappoints.

**Risk:** private API, can change without notice; failure mode is the button stopping — immediately visible, loses nothing. Mitigation is the fallback picker, not versioning. **Open:** write path unverified; delete/undo endpoint not yet located in vendor source (needed for clean spike teardown); automation-browser auth blocked (account uses Google SSO, which Google refuses in automated browsers) → either set a start.me password for a hands-free loop or keep driving reads by operator console paste. **Cost:** ~8k cached input + ~200 output per save (fractions of a cent); Anthropic key in `chrome.storage.local` — acceptable single-operator, **not** for anything multi-user. Linear: EMA-193.

---

### B133 — Migrate off the bespoke "Method" onto AWS AI-DLC v2 — ✅ **DONE 2026-08-21 [Linear EMA-194]**

**Shipped:** the lab's development workflow moved **off the bespoke "Method"** (a maintained fork of AWS AI-DLC) **onto AWS `aidlc-workflows` v2, clean** — pinned to the **`v2` branch @ `4d0968f`** (internal **v2.6.18**). `/aidlc` is now **invoke-on-demand**: 33 stages / 5 phases / 14 agents, an approval gate per stage, and a learning loop that promotes corrections into persistent rules. Artifacts land in **`aidlc/spaces/<space>/intents/<record>/`** (tracked), **not** the gitignored `aidlc-docs/`. `CLAUDE.md` dropped from **222 lines → 19** (`@AGENTS.md` + lab conventions); the engine lives in `.claude/` + root `AGENTS.md` + the `aidlc/` workspace. Design: `aidlc-docs/aidlc-v2-migration.md`.

**Why:** the fork was a **fork tax** — every upstream release forced a re-port, which is exactly what triggered this. And the overlay's *substance* turned out not to be AI-DLC at all: what actually drives quality here is this project's **DoD 8-pillar gate**, `backlog.md`, and the memory system, all of which survive untouched. The consulting framing that *was* Method-specific (mob rituals, team-ownership, engagement archetypes) is ceremony for a solo lab — **consciously dropped, not ported**. Comparative placement + decision matrix (v2 vs Method vs OpenSpec/SpecKit/BMAD vs Kiro vs nothing): [arch.md §8c](arch.md#8c-development-lifecycle-ai-dlc-v2-b133). This **supersedes** B86's "keep the Method as the spine" recommendation — the *coverage-asymmetry finding* stands unchanged (v2 spans the same full arc), only the incumbent changed; **B126** (borrow delta specs / EARS / constitution / context-engineered unit files) now targets v2's stage files and is *easier*, since `core/` → `dist/<harness>/` is an explicit customization seam the fork never had.

**Load-bearing decoupling — the move that made retirement safe.** The 3 **knowledge repositories** (engineering-knowledge · consulting-tools · industry-vertical, 517 docs) are **DATA, not workflow**: they feed 511 Bifrost KB skills, the domain-lens prompts, the DataHub glossary, and the B37 RAG corpus. They were lifted out of `.methodaidlc/` into a tracked **`knowledge-repos/`** at the repo root, with every generator repointed via a `KB_ROOT` resolver (`AIDLC_KB_ROOT` env, else self-discovery), **before** Method was retired. Verified at close-out: **511 KB skills / 116 corpus prompts / brand scrub clean**.

**Three lab deviations from stock v2 — do NOT undo (each documented in the runbook):** (1) **Bedrock env stripped** — v2 ships `CLAUDE_CODE_USE_BEDROCK=1` + `AWS_REGION` + Bedrock model IDs; the lab is **$0 Anthropic-direct**, and the workflow rules are provider-neutral (verified `0` refs). (2) **`bun` fully-qualified** (`/home/edwardmangini/.bun/bin/bun`) — hook subprocesses run under `/bin/sh` and don't inherit the shell `PATH`, so bare `bun` → `bun: not found` and the hook **silently drops** (verified `0` bare refs). (3) **Permissions hardened** — the stock bare `"Bash"` auto-allow (a permission bypass flagged in security review) removed; narrow `Bash(/…/bun ".claude/tools/"*)` allow + a deny list (`rm -rf`, `sudo`, `chmod`, `curl|sh`, `|bash`, `eval`, `base64 -d`, `dd`, `mkfs`). **An upgrade re-introduces all three** — step 4 of the runbook's *Upgrading the pin*.

**Accepted losses (documented, guarded, not bugs).** Three corpora derive from the retired Method rule tree and are now **FROZEN — registered/baked and still serving, but not regenerable from weyland**: the **52** AIDLC stage/ritual skills, the **28** `aidlc-stages` prompts, and the *stage* nodes of the baked DataHub glossary (`aidlc_glossary.py`). Recoverable in principle via the triple safety net (`~/methodaidlc-retired/` · `~/methodaidlc-retired-20260820.tgz` · the `~/IdeaProjects/method-aidlc` installer repo) by setting `AIDLC_ROOT`. **The close-out added guards, because silent zero-output is how frozen corpora rot unnoticed:** `register_aidlc_skills.py` now **exits 1** with an explanation instead of emitting a valid zero-skill loader that printed `0 created` and looked like a clean no-op; `register_aidlc_prompts.py` now **warns on stderr** that the stage lane is skipped and the correct total is **116, not 144** (it still exits 0 — its other 116 are genuinely regenerable). Both drifts were found *by this DoD sweep*, not before it.

**DoD sweep:** **docs** — new [runbooks/aidlc-workflow.md](runbooks/aidlc-workflow.md) (commands · scopes · the 3 deviations · upgrading the pin · [accepted gaps](runbooks/aidlc-workflow.md#accepted-gaps) · Method recovery · troubleshooting); substantial **arch.md §8c** + fixed the stale `.methodaidlc` glossary provenance at §7; **[runbooks/aidlc-kb-ingest.md](runbooks/aidlc-kb-ingest.md)** — corrected an **actively-wrong command** (`--src .methodaidlc` → `--src knowledge-repos`); **[runbooks/mcp-gateway.md](runbooks/mcp-gateway.md)** step 8 struck through as retired; **[concepts/spec-driven-frameworks.md](concepts/spec-driven-frameworks.md)** incumbent-changed banner + contenders row; stale docstrings fixed across 6 Python files. **Diagrams** — [flow-aidlc-workflow.md](diagrams/flow-aidlc-workflow.md) (the forwarding loop, both human turn-stops, parking); **LikeC4 N/A** — AIDLC appears there only as *data* (Neo4j/MongoDB KB), never as a deployed component. **Demo** — [demos/aidlc-workflow.md](demos/aidlc-workflow.md), ledger row 47. **`api.md` / `hosts.md` / `schedules.md` / platform-map / Port catalog: genuinely N/A** — no endpoint, host, DNS, timer, or deployed service changed; this is dev-side tooling, so §6 operational-completeness and the B82 app-registry onboarding rule don't apply.

**DoD CLOSE-OUT 2026-08-21 — pillar 7 satisfied.** The `code-scan-suite` finally ran clean after two blockers were cleared (the CPU-requests wall → **B134**, then a semgrep OOM — it defaults `--jobs` to the host CPU count and forked ~16 workers against a 2Gi cgroup, exit 137). **Result: criticals 1 → 0, non-kubescape highs 173 → 27.** The critical was **CVE-2026-64849** (MLflow unauthenticated full-read SSRF in webhook delivery) — fixed by 3.14.0 → **3.15.1** and **verified on the running pod**, not just in the repo; note the manifest pip-installs mlflow at startup, so an image-tag-only bump would have been silently downgraded on every restart. Highs fell via gitpython 3.1.58, sqlparse 0.6.0, aiohttp 3.14.3, cryptography 50.0.0, h2 4.4.1, datasets 5.0.1 across three services. All three secret scanners: **0**. Remaining exceptions are documented with dated exits in a new **`osv-scanner.toml`** (mirroring `.trivyignore`'s discipline): `lz4-java` (a `provided`-scope Maven dep that never ships in our jar) and `sqlparse 0.5.5` in weyland-dagster (capped by `dbt-core<0.6.0` → **B136**).

**The sweep also found the scanner itself was lying.** `kubescape()` read `resourceCounters` (lowercase) where kubescape emits `ResourceCounters`; the case-sensitive miss returned `{}` and fell through to counting failed CONTROLS — a plausible-looking number that tracked **kubescape's policy-set size**, not the cluster (it jumped 7 → 16 when upstream grew the set 52 → 127 controls, with nothing here changing, and reported "97 non-root containers" as **1**). Now posts `resourcesSeverityCounters` and logs the stable distinct-resource count beside it. **Expect a one-time discontinuity in the Port `code_quality` trend on 2026-08-21: the kubescape series steps 16 → 522 because the metric changed definition, NOT because posture regressed.** True posture: **119 of 347 resources failing** — 97 non-root containers, 1 hostNetwork, 1 hostPath, 1 privileged.

**Scan reports are now durable.** `/out` is an emptyDir, so every finding's detail used to die with the pod. `scan.py` now archives raw per-tool JSON + a rendered `index.html` summary (worst-first, with a Δ column diffing the previous run) to **`s3://scan-reports/<ts>/`** under a **90-day ILM rule**. Browse the JSON in Filestash; read the summary at `https://s3.weyland.lab/scan-reports/<ts>/index.html` — Filestash is a file manager and will NOT render HTML, the S3 endpoint does. See [[scan-reports-minio]].

**DEFERRED, not skipped — the demo's Part B (a full gated `/aidlc` run) is authored but unexecuted, and its live validation is tracked in B87** (the batched demo-validation sweep, ledger row 47), alongside E1–E12 which sit in the identical 🟡 authored-pending-validation state. The DoD's "a demo written but not executed is not done" bar applies to B87's close-out, which is where that execution now lives. Everything Part B *can* prove without a human at the gates was RUN 2026-08-20: `doctor` **47 passed / 0 failed**, 0 graph cycles, 33 stages topo-ordered, `scope-table --check` clean, Bedrock-strip and absolute-bun checks both 0, and the decoupling regression green (511 KB skills / 116 prompts).

**Part B was reshaped after a failed first attempt, and the failure is the lesson.** The original draft said "run on a deliberately trivial task" under `poc` scope. That stalls: `intent-capture` (scopes `enterprise`/`feature`/`mvp`/`poc`) is a **discovery** stage asking what business problem this solves and who the stakeholders are — an invented task has no honest answers. Two fixes: (1) a demo **demonstrates, reproducibly, on demand** — it is not a vehicle for real work, so "run it against the next real backlog item" was rejected as non-reproducible; (2) use **`bugfix` scope**, which skips discovery entirely, so the questions are about the defect rather than business intent. Part B now creates a **disposable `/tmp` fixture** (a shell script dividing by zero on an empty file — reproduction verified), fixes it through the workflow, and tears everything down. The attempt also surfaced two real engine hazards, both fixed: `intent-create` **auto-migrated a legacy flat workspace**, sweeping the entire gitignored `aidlc-docs/` (79 files) into a tracked intent dir on a public repo (restored; the Method-era `aidlc-state.md` that triggered it renamed to `aidlc-state.method-archive.md`), and Method-era state carries no `State Version` for the v8 graph so it could not advance.

Linear: EMA-194. Memory: [[aidlc-v2-migration]]. Supersedes [[methodaidlc-user-authored]] + [[feedback-aidlc-not-superpowers]]. See [[bifrost-skills-repo]], [[spec-driven-frameworks-b86]], B37 (KB ingest), B86 (framework eval), B126 (borrow the notations).

---

### B134 — CPU request management: right-size reservations + move more systems on-demand — 🔴 **HIGH (2026-08-20)**

mother's CPU **requests** are over-committed while the node sits nearly idle — a scheduling wall, not a capacity problem. **Measured 2026-08-20: 16 cores allocatable, ~17.1 reserved, ~19% actually used.** The busiest pod in the entire cluster uses **0.12 cores**; the top ten combined ≈ **0.58**. Roughly **14 cores of reservation are fiction**, and the scheduler refuses new pods while ~80% of the CPU idles.

**It has already broken two things, both silently.** (1) `code-scan-suite` sat **Pending 40+ min** — `FailedScheduling: 0/1 nodes are available: 1 Insufficient cpu`, no preemption victims; it asks for only 250m, and no request size would have helped because the node was past its ceiling before the scan asked for anything. (2) **A postgres backup was missed** — `postgres-backup` shows `lastScheduleTime 2026-08-20T03:30Z` against `lastSuccessfulTime 2026-08-19T03:42Z`; the pod could not schedule at 03:30 and died on `activeDeadlineSeconds`. That one surfaced *only* as an Argo "Degraded" badge that reads as cosmetic — **a missed database backup presenting as a UI annoyance.** Neither had an alert.

**Not new.** `k8s/data-mesh/flink-session.yaml` already carries the comment *"node CPU-requests are saturated; JM is coordination-only, runs fine throttled (lab)"* — the JobManager was trimmed to 0.25 for exactly this reason. Same class as [[istiod-request-node-wall]] (the memory-requests wall from istiod over-reservation). We keep treating symptoms one manifest at a time.

**Symptom relief already applied (2026-08-20):** `llama-guard` `cpu: "1"` → **100m** (reserved a full core, uses <0.03, and has **no CPU limit** so inference still bursts freely — frees ~0.9) and `code-scan-suite` `250m` → **100m** (batch job, no latency SLO; a large *reservation* buys it nothing).

**The actual work:** (1) **fleet-wide right-sizing** — compare `kube_pod_container_resource_requests` against real `container_cpu_usage_seconds_total` per pod and bring reservations near observed p95 (~50 pods, most reserve 0.25 and use ~0); (2) **move more systems on-demand** — the `store-scaler`/KEDA wake-sleep mechanism already exists for Tier-2 stores, so extend the pattern (candidates seen awake and idle: `ray-head` up 7d, `promptfoo`, `neodash`, `a2a-inspector`, `kokoro`, Flink taskmanagers) — **a sleeping pod reserves nothing, which beats trimming**; (3) **alert before it bites** — a `FailedScheduling`/Pending-duration alert to Telegram, since both failures today were silent and one was a missed backup (DoD §6 "Triggered": a thing that must stay fresh needs a freshness signal); (4) **question whether requests are the right tool at all** on a single-node $0 lab — they exist for bin-packing across nodes, and with one node they mostly manufacture artificial scarcity, so a deliberate convention (tiny requests, limits where it matters) may beat per-service tuning.

**Measurement gotcha — keep this.** `sum by (pod) (kube_pod_container_resource_requests)` **double-counts**: both kube-state-metrics *and* opencost publish it — pin `job="kube-state-metrics"`. A `node=` filter still includes terminal (Succeeded/Failed) pods that no longer reserve anything. When in doubt, trust the scheduler's own `FailedScheduling` message over a reconstructed sum.

Linear: EMA-195. Surfaced during the B133 DoD sweep. Relates B130 (backups), [[store-scaler-easy-button]], [[istiod-request-node-wall]], [[node-oom-forensics]].

---

### B135 — Automate the image build→deploy cadence (script / skill / agent) — ✅ **DONE (2026-08-23)**

**Shipped: `scripts/ship-images.sh`** — the seven-step hand-run loop is now one command with machine gates. It short-circuits without triggering a pipeline when nothing changed, triggers and polls Woodpecker, closes superseded bump PRs, merges the new one only under three conditions, syncs **only the affected** Argo apps, then verifies against the live cluster. Approval did not disappear; it stopped being a human click. In a solo lab reviewer, approver and on-call are the same person, so a click adds no independent judgement — the gate replaces it with something that cannot be absent-mindedly waved through.

**The three merge conditions, and they are NOT equally strong** — stated plainly because treating them as three defences is the mistake: **same-repo, not a fork** is decided by GitHub and is unspoofable (the load-bearing one — `weyland-lab` is public with no branch protection, so it is the only thing between a stranger's PR and `main`); the **`weyland-ci` author name** is a *convention* set by `git config` and proves nothing alone; the **tags-only diff** is written as "no line fails to match", so a smuggled `memory: 8Gi` fails even though the diff still contains valid tag lines.

**Verification is part of the deploy.** FR1.5 asserts **every** bumped image is live on a pod — the first green run printed `✓ shipped` while `weyland-tool-server` was still on the old tag, because the check passed on one matching pod. A **SMOKE** gate now additionally requires every bumped workload to declare a `readinessProbe` and report all replicas available, which makes the probe a shipping requirement rather than a nice-to-have.

**Seven defects that 47 green tests could not find, all caught by three live runs.** Five were **one bug class — an absent or failed result standing for success** — and two of those were *inside the gate built to prevent it*: `woodpecker-cli --output json` silently ignored; `curl -sf` collapsing every non-2xx to 0; `NOERROR` matching `/error/`; a shallow-clone `git diff` failure read as "changed" (**change detection had never worked in CI** — all 11 images rebuilt nightly while the log printed per-image decisions that looked deliberate); and `rm -f "$diff_file"` running *before* the gate that read it, so FR1.5 passed vacuously on an empty list. Also: FR2.1 originally keyed on PR author `weyland-ci`, which is not a GitHub account; and cleanup deleted a valid PR's branch, which auto-closed PR #33.

**Deployment health sweep found `dagster-user-code` had no `readinessProbe` at all** — the gRPC code server every Dagster run executes inside, `Recreate` strategy, peaks at 10.6 Gi. Its `1/1 Ready` meant only that PID 1 had not exited. Probe added; `feast-server` upgraded from `tcpSocket` to a verified `httpGet /health`.

**Observability: the estate had 41 alert rules and every one watched something that WAS running.** Nothing fired when scheduled work simply did not happen — which is how `nightly-images` sat `enabled: false` for four days while `docs/schedules.md` documented it as daily. Two watchdogs close it: `k8s/monitoring/cron-freshness-rules.yaml` (per-cadence budgets over `kube_cronjob_status_last_successful_time`, a metric that already existed with no consumer, plus an `absent()` companion) and `k8s/pr-lifecycle/cron-freshness.yaml` (a CronJob asking the **Woodpecker API**, because a Woodpecker cron is not a Kubernetes object and kube-state-metrics can never see it).

**Tests: 0 → 62.** This repo had no shell test harness at all when the work started; `bats` is now a blocking CI step.

**Shipped:** `scripts/ship-images.sh` · `scripts/ci/detect-changes.sh` (shallow-clone fix) · `scripts/ci/open-deploy-pr.sh` · `scripts/tests/{ship-images,pr-staleness,cron-freshness,open-deploy-pr}.bats` · `k8s/monitoring/cron-freshness-rules.yaml` · `k8s/pr-lifecycle/cron-freshness.yaml` · `k8s/argocd/argocd-lan.yaml` · probes on `k8s/dagster/user-code.yaml` + `k8s/data-mesh/feast-server.yaml` · sealed `cron-freshness-woodpecker` · docs: `arch.md` §10b + §6 + §9, `runbooks/ship-images.md`, `runbooks/pr-lifecycle.md`, `diagrams/flow-ship-loop.md`, `demos/ship-images.md`, `schedules.md`.

**Residual, tracked not hidden:** **B135 phase 2** — nine images outside `images.tsv` (`weyland-operator`, `weyland-mcp-gateway`, `weyland-mcp-compositor`, `weyland-guard`, `weyland-agent`, `realm-of-agents`, `ray-head`, `a2a-inspector`, `mcp-server-datahub`) are hand-built and uncovered; until they are in, the loop reports success while a third of the fleet is unwatched. **B140** (smoke layer that exercises a real transaction), **B139** (measured: worst 11-image build 15m14s vs a 77-minute window — no collision), **EMA-77** (the demo's three unrun live paths, deferred by decision).

**DoD:** pillars 1, 2, 4, 6 pass; 3 is 🟡 with live execution deferred to EMA-77; 7 partial (the 19-tool `run-scan-suite.sh` still to run on mother); 8 (cascading changes) graded at close-out — it surfaced the freshness rule missing **the watchdog itself**, a stale `applications.yaml` reason, and three unrelated backup CronJobs with no `schedules.md` row running on the wrong clock.

Linear: EMA-196.

Shipping one image change is a **seven-step loop run entirely by hand**, and three of its steps fail **silently** — you find out two steps later via a confusing result, not at the point of the mistake. Run five times on 2026-08-20, it stumbled four; every stumble was a skipped step, not a real fault.

**The loop:** (1) `git push` — **silent**; (2) trigger the pipeline; (3) CI builds + opens a **PR**; (4) **merge the PR** — **silent**; (5) `git pull` — **silent**; (6) Argo reconciles (~3 min poll, **no LAN webhooks** — [[lan-no-github-webhooks]]); (7) run the thing.

**How each silent step actually bit us.** **(1)** the pipeline was triggered before the push landed, so `detect-changes` — which diffs the build context against `HEAD` *at pipeline start* — rebuilt the OLD `scan.py` and produced an image that looked new and behaved old; cost a full cycle to spot. **(4)** Argo was refreshed repeatedly expecting a change with nothing merged; separately **PR #12 sat open a full day**, leaving the whole 11-image fleet two builds behind while every surface read green (the pipeline goes green at *"opened a PR"*, and `notify-port` reports the **pipeline** outcome, never the merge). **(5)** merging remotely leaves local behind, and the CI's PR edits the same manifests being edited locally, so the next push conflicts. **(6)** the scan was run twice before the sync landed → old image, twice.

**The pattern is the point:** steps 1, 4 and 5 emit no signal when skipped. Nothing says "you didn't do this" — you get a wrong-looking result later and debug the wrong layer. Same class of silent-gap failure as B131 (open PRs rotting unseen) and B134 (a scheduling failure surfacing only as a stale Argo badge).

**What it should do — one invocation that refuses to advance past a gate it cannot verify:** confirm the tree is pushed and `HEAD` matches `origin/main` **before** triggering (this alone kills the most expensive failure); trigger + poll, surfacing the failing step's log; find the opened PR (its sha differing from the deployed tag **is** the proof the change was picked up); merge it and **close any superseded older image-bump PR** (merging an older one after a newer rolls images *backwards* — the #12-after-#13 trap); `git pull`; force a **targeted** Argo reconcile with the `argocd` CLI (`argocd app sync <app>` per affected app — **never** the `argocd.argoproj.io/refresh=hard` annotation or a `kubectl patch` on the Application CRD, both of which `docs/runbooks/argocd.md` forbids; and never `--all`, since a full re-compare across 79 apps is a CPU spike on a node that already has a request wall, B134). *Amended 2026-08-22: the original text here proposed the forbidden annotation. The CLI is the runbook's own documented mechanism and is a new prerequisite on the dev machine — see docs/runbooks/ship-images.md.*; then **verify the live cluster resource carries the new tag before declaring done** — the running pod is the only proof, the repo and the PR are not.

**Mechanism undecided:** a shell script (`scripts/ship-images.sh` — simplest, matches `run-scan-suite.sh`, no new dependency) · a Claude Code skill (`/ship` — could derive which apps a diff touches instead of hardcoding) · an agent (heaviest; only if the loop needs judgment beyond gate-checking). **Bias to the script** until something demands more: the value here is **verified gates**, not intelligence.

**Acceptance:** one command takes a pushed change to a verified rollout; every gate is checked and a skipped/failed one **halts with the specific reason** instead of proceeding; verification is against the **live cluster resource**; superseded image-bump PRs are closed automatically.

Relates B57a (the image CI this wraps), B131 (open-PR lifecycle), B134 (why the refresh is targeted), [[weyland-image-ci-b57a]], [[argocd-gitops-gotchas]].

---

### B136 — Bump dbt-core 1.11.12 → 1.12.x (unblocks sqlparse 0.6.0 in weyland-dagster) — 🟡 **MEDIUM (2026-08-20)**

`dbt-core==1.11.12` pins `sqlparse<0.6.0,>=0.5.5`, which **blocks the sqlparse CVE fix** in `services/weyland-dagster` — build 19 died on exactly that (`ResolutionImpossible: dbt-core 1.11.12 depends on sqlparse<0.6.0`). **dbt-core 1.12.3 relaxes it to `sqlparse<0.7.0`**, so the bump IS the fix.

**Why deferred, not bundled:** the sqlparse change rode a CVE sweep, and dragging a dbt-core *minor* into that couples a security fix to the tool that builds all 7 marts — it pulls `dbt-adapters` / `dbt-trino` / `dbt-metricflow` / `dbt-semantic-interfaces` with it. That needs its own validation pass. `services/genre-trainer` has no dbt and IS on 0.6.0, so this is a dagster-only constraint, not a decision to skip the fix.

**What it unblocks:** 5 DoS-class CVEs currently accepted in `osv-scanner.toml` (8 osv findings) — CVE-2026-59893, CVE-2026-54284, CVE-2026-71491, CVE-2026-59894, GHSA-cfqr-cjx5-5jcm, all quadratic-CPU paths in the lexer/grouping/reindent. Real exposure is low (dbt parses **our own** model SQL from the repo; these CVEs need attacker-controlled input), which is what makes deferral defensible — but the fix exists, so this is **a deferral with a date, not a permanent accept**.

**Acceptance:** dbt-core → 1.12.x with its siblings moved to compatible versions; `sqlparse==0.6.0`; **DELETE the `[[PackageOverrides]]` sqlparse block from `osv-scanner.toml`** (it is scoped to `version = "0.5.5"` so it stops applying by itself, but a dead exception left behind is drift); validate with `dbt deps` + `parse` + `build` + tests against the marts (the image bakes a `dbt parse`, so a broken manifest fails the build — necessary but **not** sufficient, the mart tests are the real check); confirm `weyland_dbt_assets` still materialises and dbt-docs still renders.

Linear: EMA-197. Relates B1.5 (dbt transform tier), B131 (dependency lifecycle), B133 (the sweep that surfaced it). Detail: `osv-scanner.toml` → sqlparse override.

---

### B141 — `rta-trending` FlinkSessionJob emits a permanent `Job Not Found` Warning — 🟡 **LOW (2026-08-23)**

**Root-caused 2026-08-23; the remedy is a design call, not a bug fix.** `rta-trending` is a **bounded** job by design (`scan.bounded.mode=latest-offset`): it reads the lastfm topic to the end, closes its tumbling windows, writes `analytics.trending_artists`, and finishes. It did — 5,017,946 rows across 223 snapshots, last committed **2026-08-21T21:50:56Z**. The session cluster is healthy: the JobManager is running the CDC flagship (`4416a6ca…`) and health-state-risk (`2b946762…`), both checkpointing every 60s without failures.

So the Warning is the Flink Kubernetes Operator reconciling a `FlinkSessionJob` CR whose job has legitimately terminated. It has nothing to adopt, so it emits `Missing / Job Not Found` **forever**.

**Why it is worth closing despite not being an outage:** a permanent Warning stream is how a team learns to ignore Warning events. Same alert-fatigue shape as `nightly-images` sitting `enabled: false` for four days while `docs/schedules.md` described it as running daily.

**Terminal state confirmed `FINISHED` (operator-checked 2026-08-23).** The job succeeded. There is no failure to chase — the CR describes work that is complete, and the Iceberg commits through 2026-08-21T21:50:56Z are its output. The Warning is purely the operator being unable to retire a CR whose job has legitimately ended.

**Options, now that FINISHED is known:** delete the CR (safe — the data is written and the run is archived to `s3://warehouse/_flink/completed-jobs`; the cost is losing the GitOps record of how the job was run, which could be kept as a commented manifest or a runbook snippet); or keep it and document the Warning as expected in the Flink runbook. A scheduled re-run is the wrong shape — the manifest frames this as a one-shot showcase (*"the continuous flagship is the CDC job"*), so freshness was never its job.

Recommendation: delete the CR and record the submission recipe in the Flink runbook. A permanent Warning that everyone is told to ignore is worse than a documented procedure for re-running a demo job.

**Second finding, same investigation:** the `k8s-mcp` service account cannot read `flink.apache.org` resources at all. Read-only diagnosis of the streaming tier is impossible from the MCP fleet. Worth a RBAC read grant on its own merits.

Linear: TBD. Relates **B83** (streaming tier, owns this manifest), B135 (the deployment-execution health sweep that surfaced it), B49 (observability).

---

### B140 — Smoke-test layer: prove a deploy WORKS, not just that it is Ready — 🟠 **MEDIUM (2026-08-23)**

**What B135 already fixed, so this starts from a real floor.** The ship loop's SMOKE gate now requires every bumped workload to declare a `readinessProbe` and report all replicas available, `dagster-user-code` got the probe it never had (`tcpSocket 4000`), and `feast-server` moved from `tcpSocket` to a verified `httpGet /health`. That converts `Ready` from "PID 1 is alive" into "something asked and got an answer".

**What is still missing:** nothing anywhere in the loop exercises a **user-visible transaction**. A readiness probe proves the process answers; it does not prove the process is correct. Concretely:

- `dagster-user-code`'s probe is TCP, so it proves the gRPC server is **listening**, not that its definitions **loaded**. A code server that binds 4000 and fails to load definitions still passes.
- `dbt-docs` serving `/` says nothing about whether the docs it serves are current.
- No feature is ever fetched from Feast, no Dagster run is ever launched, as part of shipping.

**Acceptance:** one real transaction per shipped service, run after FR1.5 and before `✓ shipped` — e.g. a Dagster GraphQL query asserting the code location loaded without error (this is the one that closes the TCP-probe gap), and a `POST /get-online-features` against Feast for a known entity key.

**Constraint that shaped the current design and will shape this one:** almost every UI sits behind Keycloak forward-auth and answers an unauthenticated curl with 307 — measured 2026-08-23 for `dagster.weyland.lab`, `dbt-docs.weyland.lab`, `flink.weyland.lab`, `flink-history.weyland.lab`. Only `feast.weyland.lab` answers directly. Any HTTP-based smoke layer therefore has to either run in-cluster or carry a credential into the ship path; the second option puts Keycloak in the deploy critical path and should be argued for explicitly, not drifted into.

**Do not regress:** the SMOKE gate fails closed on an empty workload table and NAMES images it did not check. Preserve both — five of the seven original `ship-images.sh` defects were an absent result read as a positive one, and one of the five SMOKE tests initially passed against no implementation for exactly that reason.

**Companion gap, found 2026-08-23 during the B135 DoD close-out — CronJob FAILURE is still unalerted.** `cron-freshness-rules.yaml` watches `kube_cronjob_status_last_successful_time`, i.e. **absence** of success. A run that **fails and then succeeds** inside its budget is invisible to it. Evidence: `dagster-freshness-check-29791170` sat `Failed` in ns `weyland` for 19h; later runs succeeded, so freshness stayed green and nothing alerted. By the time it was noticed the pod and its events had both aged out, so the cause is unrecoverable — the failure mode this whole effort exists to remove, one layer over.

`DataMeshBackupFailed` (`kube_job_status_failed{namespace="data-mesh", job_name=~"(minio|pg)-backup.*"} > 0`) is the only failure-side rule in the estate and is scoped to two backup jobs. Generalising it to the other nine CronJobs is a handful of lines and completes the pair: **freshness catches "it stopped", a failure rule catches "it ran and broke".** Keep them separate rules — collapsing them hides which of the two happened.

Linear: TBD. Relates **B135** (added the gate this extends), B131, B49 (observability), B1.8 (Feast).

---

### B139 — Overnight window collision: nightly image build vs the 02:17 ingestion — 🟡 **LOW (measured 2026-08-23; was MEDIUM)**

**Measure first, then decide.** The `nightly-images` Woodpecker cron fires at **01:00 NY**; `weyland_ingestion_job` fires at **02:17**. That is a **77-minute window**, and nobody knows how long a three-image build takes — the cron was created `enabled:false` on 2026-08-18 and had never run until it was enabled 2026-08-22, so there is no cron-triggered duration on record.

**Why the overlap matters — measured 2026-08-22, 14-day peaks vs requests:**

| Pod | Request | 14d peak | Exceeds request by |
|---|---|---|---|
| `dagster-user-code` | 4 Gi | **10.6 Gi** | +6.5 Gi |
| `trino` | 3 Gi | 8.0 Gi | +5.1 Gi |
| `tempo-0` | 512 Mi | 3.9 Gi | +3.4 Gi |
| `neo4j` | 1 Gi | 4.0 Gi | +3.0 Gi |

The lab runs a deliberate memory overcommit — nearly everything is `Burstable` with requests well under peak — and it holds because the peaks do not coincide. The kubelet evicts by **usage minus request**, so under pressure the first pod killed is whichever most exceeds its reservation. During ingestion that is `dagster-user-code`, at exactly the moment it is doing real work. A build still running at 02:17 is the collision.

**Do this:** read the first cron-triggered build's duration from Woodpecker (`woodpecker-cli pipeline ls edtbl76/weyland-lab`, look for `event: cron`). If it lands within ~60 min there is adequate margin. If it approaches 77 min, move the cron earlier (`0 4 * * *` UTC = 00:00 EDT / 23:00 EST — still inside the 00:00–06:00 off-hours window, Design Rule #1) rather than moving ingestion.

**Explicitly NOT the fix — both were considered and rejected 2026-08-22:**
- **Trimming requests.** Only **8.1 Gi** is genuinely over-reserved (request above the 14-day *peak*), spread across many pods with a largest single win of 731 Mi. An earlier "15.5 Gi over-reserved" figure was an artifact of comparing requests to one idle `kubectl top` sample — `dagster-user-code` reads 938 Mi at rest and 10.6 Gi under load. **Never size a job runner from an instantaneous sample.**
- **Store sleep via Argo `ignoreDifferences` on `/spec/replicas`.** Stays parked, on mechanism not arithmetic: the carve-out is unscoped and permanent, so a sleeping store reports Synced/Healthy, the accidental-scale-to-zero safety net disappears, and the sleep state lives only in the cluster (the B137 disease). See `docs/runbooks/port-agent-easy-button.md` § PARKED. If store sleep is ever wanted, the clean form is `replicas: 0` **committed to git**, which keeps every property.

**MEASURED 2026-08-23 — no collision. Do NOT move the cron. Downgrading to 🟡 LOW / watch-only.**

The first cron-triggered build fired on schedule: pipeline **#25**, `event: cron`, `success`, started **05:00:21Z** (01:00:21 EDT), finished **05:01:43Z** — **82 seconds**.

**But 82s does not answer the question**, and reporting it as "the build duration" would have been a false result. Its own log:

```
[detect] HEAD=73452fd9 → candidate tag git-73452fd9
[detect] shallow clone — deepening so the old shas are reachable
[detect] weyland-tool-server: unchanged since git-36c4d3e0 — skip     (×11)
[detect] 0 image(s) to build
[build]  empty plan — nothing to build.
[handoff] no images built — nothing to deploy.
```

Zero images built, so 82s measures the **no-op floor**. The real numbers come from runs that actually built, and the build work is identical — only the trigger differs:

| Pipeline | Images built | Duration | Cache |
|---|---|---|---|
| **#20** (08-21 04:01Z) | **11** | **914s = 15m 14s** | cold — **worst observed** |
| #22 (08-23 01:51Z) | 11 | 316s = 5m 16s | warm |
| #24 (08-23 02:25Z) | 3 | 75s = 1m 15s | hits; retag + push |
| #25 (08-23 05:00Z, cron) | 0 | 82s = 1m 22s | no-op floor |

**Worst observed full 11-image build is 15m 14s against a 77-minute window — 19.8% of it, with 62 minutes of headroom.** Even 3× that worst case still lands before 02:17. Note #24 built three images *faster* than #25 built zero: the ~70–85s fixed overhead (clone, yamllint, repo guards, shellcheck, 62 bats, 28 pytest, kubeconform) dominates, and BuildKit's registry cache makes unchanged image work nearly free.

**Nothing was OOMKilled or evicted by the build.** No `Evicted` events. Exactly two real restarts in the surrounding 15 hours, neither in the 05:00:21–05:01:43Z build window:

| Pod | Restart window | Local | Attribution |
|---|---|---|---|
| `rag-index-pgvector` | 02:30–03:00Z | 22:30–23:00 EDT | hours before the build |
| `trino` (**OOMKilled**) | 06:30–07:00Z | **02:30–03:00 EDT** | 15–45 min INTO the ingestion window — the 3 Gi-request / 8 Gi-peak row in the table above, caused by ingestion, not by the build |

> **Measurement trap worth keeping.** `sum by (pod) (increase(kube_pod_container_status_restarts_total[30m]))` reported a restart for **~60 pods simultaneously** at 04:00:00Z — an apparent cluster-wide event. It is an artifact: `monitoring-kube-state-metrics` restarted, every series it publishes reset to zero, and PromQL attributed the re-climb as fresh increase for every pod at once. The raw counters disprove it (keycloak flat at 19, neo4j flat at 18 across the whole window). **Check the raw counter before believing an `increase()` spike that lands on many series at the same instant.**

**Why the cron stays at `0 5 * * *` UTC:** moving it to `0 4 * * *` was the prepared remedy, but there is no collision to remedy. Moving a schedule on the strength of a no-op measurement would be acting on nothing, and 01:00 EDT is already placed to clear the 02:00 scaledown.

**Residual risk, bounded not ignored:** `weyland-image-prune` (Sun 11:00) removes unused images from the node, so a Sunday-night build starts colder than #20 did. Even so, #20's 914s cold-cache figure has 5× headroom. The real gap is that **build duration is not monitored** — a regression would be invisible until it collided. Now that a baseline exists (11 images: 914s cold / 316s warm), a static threshold is writable; see `anomaly-config.md` in the observability-setup record, which deferred exactly this for want of a measurement.

**Item 5 could not run.** The cron build opened **no bump PR** (nothing changed), so the "first live `scripts/ship-images.sh` run against a cron-produced PR" has nothing to run against. It needs a night where an image build context actually changes.

Linear: TBD. Relates B134 (the request wall), B57a (the nightly build), B135/B131 (the ship loop that made this visible), B137 (live-only config), B140 (the smoke layer that would extend this verification).

### B138 — Repo coverage parity: every active repo tracked across the whole toolset — 🟠 **MEDIUM (2026-08-22)**

**The problem:** the lab has **six active repos** — `edtbl76/Algopedia`, `ServiceTransformation`, `emangini-tailwind-nextjs-contentlayer`, `startme-curator`, `stud.io`, `weyland-lab` — and every tool that watches repos watches a *different* subset. Nobody decided that; each tool was onboarded once, against whatever set was current that day, and none of them agree now.

**Known divergence, found 2026-08-22 while wiring B131:** the `github-weyland` Port integration maps a six-repo set that carries `midi_real_book` but **not** `startme-curator`. The B131 staleness watchdog's PAT covers a six-repo set that carries `startme-curator` but **not** `midi_real_book`. Two "complete" six-repo lists, neither the same, both looking authoritative from inside their own tool. `midi_real_book` also does not appear in the active set above, so at least one of those lists is watching something retired.

**Why it matters:** this is the same failure class as B137 and as B131 itself — coverage that *looks* total from inside one tool while something real goes unwatched, and nothing anywhere compares the lists. A scanner that runs on five of six repos reports all-green exactly like one that runs on six.

**Scope — establish ONE canonical repo list, then reconcile every consumer to it:**

| Lane | Tool | What to check |
|---|---|---|
| CI/CD | Woodpecker | which repos are activated; which have crons; are the crons **enabled** (B137 found `nightly-images` created `enabled:false` and silently dead for 4 days) |
| Catalog | Port `github-weyland` Ocean integration | the `repository` + `pull-request` kind selectors |
| PR lifecycle | B131 `pr-staleness-check` | `PR_REPOS` in `k8s/pr-lifecycle/pr-staleness.yaml`, and the PAT's own repo grants |
| Code review | the B106/B118 7-tool AI review stack (DeepSource, CodeScene, Sourcery, …) | B118 established parity on `weyland-lab` + `stud.io` only — the other four are unconfirmed |
| Security/quality | `code-scan-suite` (19 tools), SonarQube, `sonar-scan` CronJob | which repos are actually scanned vs assumed |
| IaC | `tofu/github/` | which repos are declared at all |

**Acceptance:** a single declared source of truth for "the active repos" that lives in git; every lane above either matches it or carries a written, reasoned exception; and a **drift check** that fails when a lane's set diverges — same posture as `check-app-registry.sh`, which is what actually catches this class rather than a periodic human sweep. Retired repos (`midi_real_book`?) explicitly retired, not silently dropped.

**Not in scope:** onboarding new tooling to any repo. This is about knowing and reconciling what is already claimed.

Linear: TBD. Relates **B131** (surfaced the divergence), **B137** (same disease — live-only config nobody can diff), B106/B118 (the review-stack parity claim this would verify), B57a/B57b (Woodpecker's mixed fleet), B60/B82 (Port catalog completeness).

### B137 — Bring live-only config back under IaC (Port schema + Woodpecker) — 🔴 **HIGH (2026-08-22)**

`docs/runbooks/port.md` documents the B60 split as **"blueprints (the schema) = OpenTofu, drift-checked; entity data outside."** That is no longer true. Verified against the live `api.port.io` on 2026-08-22:

| | In `tofu/port/` | Live in Port |
|---|---|---|
| Blueprints | 13 | **51** |
| Scorecards | 0 | **8** |
| Integrations | 0 | **4** |

**38 blueprints, all 8 scorecards, and all 4 integrations exist only in Port's UI.** There is no codified definition of any of them, no `tofu plan` that would detect their loss, and no review trail for changes to them.

**Concrete consequences already observed:**

- The `component` blueprint's `service` relation (`catalog.tf:442`, titled "Repo / Service (DORA)") targets a `service` blueprint **that does not exist in `tofu/port/`**. It resolves only because a `service` blueprint exists in Port with 6 entities — created outside OpenTofu. Reading the IaC alone, that relation looks broken.
- Eight scorecards carry real logic with no source of truth: `service/delivery_performance` (14 rules), `service/production_readiness` (10), `service/quality_maturity` (5), `service/reliability_health` (5), `service/dora_lead_time` (3), `service/dora_deploy_freq` (3), `workload/availability` (3), `sonarQubeProject/services_connected` (1). Losing the org loses all of it.
- Four integrations are unversioned config: `github-weyland` (github-ocean 6.8.1, mapping **only** `repository`), `weyland-cluster` (OnPrem K8S EXPORTER 0.7.4, 11 kinds), `linear` (0.3.97), `sonarqube-direct` (0.1.439).

**How this was found — worth recording, because the failure mode repeats.** During B133's reverse-engineering scan the codebase was grepped for `pull_request` and, finding nothing, the store concluded Port had no PR ingestion and "cannot easily get one." That conclusion was wrong: Port's configuration does not live in this repo, so the repo could never have answered the question. `githubPullRequest` exists as a blueprint and `github-weyland` is live and ingesting — PR ingestion is one mapping line away. **Grepping the repo cannot establish the absence of anything Port owns.** The codekb finding was withdrawn (TD-3 → TD-3b) and `docs/runbooks/port.md` corrected.

**Also surfaced:** the runbook claimed LAN-only topology meant "no self-hosted k8s exporter / Ocean integration running." There is one — it runs on-prem and pushes **outbound**, so inbound unreachability was never the constraint. Corrected 2026-08-22.

**Not to be bundled into B131.** Codifying an integration means importing `github-weyland` into OpenTofu state — a real operation on a live OAuth-connected integration currently feeding 6 repositories. That risk should not ride along with a one-line mapping change.

**Acceptance:** every blueprint, scorecard and integration the lab depends on is defined in `tofu/port/`; `tofu plan` reports no drift; the `service` blueprint exists in code so the `component` relation resolves from the IaC alone; a documented decision for anything deliberately left UI-managed (with the reason); **and every codified item validated by a positive assertion against the LIVE system** per the table below — a clean `tofu plan` only proves the code matches the code. Bonus: `deployment` currently has **0 entities**, starving three DORA scorecards — that is EMA-172's gap, not this item's, but B137 is what makes the scorecard definitions reviewable.

**UPDATE 2026-08-22 — two more UI-side changes made, both now part of what B137 must codify.** Fixing the findings above required live API changes to two integrations, neither of which exists in git:

1. **`github-weyland`** — added the `pull-request` kind to its mapping (it previously mapped only `repository`), with a selector scoped to the same six repos and a `repository` relation on `.base.repo.name`. `githubPullRequest` went 0 → **7 entities**, matching `gh pr list`. Two traps found on the way: `POST /v1/integration/<id>/resync` runs an **incremental** sync, which fetches only what changed and can never backfill pre-existing records (`0 entities out of 0 raw results` in the logs); and a top-level `{"incrementalSyncEnabled": false}` PATCH returns HTTP 200 while being **silently ignored** — the flag lives at `spec.appSpec.incrementalSyncEnabled`. Toggling it there, resyncing (`0 entities out of 43 raw results` → 7 registered), then restoring it is what worked.
2. **`weyland-cluster`** — added `batch/v1/jobs` and `batch/v1/cronjobs` to the k8s exporter. Its `v1/pods` resource relates non-ReplicaSet-owned pods to `k8s_workload` by `<name>-<Kind>-<ns>-<cluster>`, but no resource created the Job workloads, so every CronJob pod failed its relation. **This was generating ~40 audit-log failures/hour continuously — 1000 in 25 hours, 963 of them this one cause** (dagster-freshness-check every 30m, postgres-backup, lancedb-sync, pg-backup). After the fix `k8s_workload` holds 23 Job entities and the failure rate is **0 in the following 10 minutes**.

**UPDATE 2026-08-22 (b) — the scope is wider than Port: Woodpecker's own config is live-only too.** Found while fixing the B135 ship loop. Same disease, different system — configuration that only exists inside a running service, invisible to `git`, with nothing to detect drift:

3. **`nightly-images` cron was created `enabled: false` on 2026-08-18 and had never fired.** `next_exec` was frozen at its first-ever slot and every one of the 21 pipelines on `edtbl76/weyland-lab` was `event: manual`, while `docs/schedules.md` documented a running daily build for four days. Enabled 2026-08-22 via `PATCH /v1/... /api/repos/2/cron/2` (the CLI's `repo cron update` 404s on a positional repo argument, as `pipeline last` does). **This fix is live cluster state and exists nowhere in git** — Woodpecker's DB is a SQLite file on a PVC, so a rebuild loses it silently. `--enabled` is not a default and a disabled cron emits nothing at all.

**Validation is mandatory, not optional, for every item above.** This whole class of bug is "something was configured and nobody checked" — so codifying it in IaC without proving the codified version actually works just relocates the problem. Each item needs a positive assertion against the live system after the IaC applies, not a green `tofu apply`:

| Item | The assertion that proves it |
|---|---|
| `github-weyland` `pull-request` kind | `GET /v1/blueprints/githubPullRequest/entities` count **matches `gh pr list`** across the six mapped repos, and one entity spot-checked for a resolving `repository` relation |
| `weyland-cluster` jobs/cronjobs | `k8s_workload` contains Job entities, **and** `GET /v1/audit-log?status=FAILURE` over the following hour is far below the ~40/hr baseline |
| `incrementalSyncEnabled` | ~~reads `true` after the backfill~~ **superseded 2026-08-23 — see update (d): the polarity was backwards.** Reads **`false`** at `spec.appSpec.incrementalSyncEnabled`, deliberately, so scheduled resyncs run FULL and reap closed-PR entities. `true` is what let stale entities accumulate. Note the flag is not durable: the SaaS integration re-registers and overwrites it |
| `nightly-images` cron | `enabled` is `true` **and `next_exec` is in the FUTURE** — a stale `next_exec` is the only tell that a cron has stopped, and it is what would have caught this four days earlier |

A `tofu plan` with no drift proves the code matches the code. None of the four rows above are visible to it.

**UPDATE 2026-08-23 — the PR-ingestion work is COMPLETE, and three of the assumptions above were wrong.** Verified against the live API, not inferred:

**a. The backfill had already happened.** `githubPullRequest` held **8** entities, not the 0 recorded on 2026-08-22. Live GitHub had 7 open PRs (stud.io 3, midi_real_book 3, emangini-tailwind 1; Algopedia / ServiceTransformation / weyland-lab 0). Port now matches **exactly at 7**.

**b. The 8th was a stale entity our own ship loop created.** `4340557995` = `weyland-lab` PR **#34**, status `open`, `closedAt: null` — the PR `ship-images.sh` FR2.3 **closed as superseded** at 02:15 before merging #35. Port ingested it while open and never learned it closed, because the integration fetches **only open PRs** (`[Rest] Fetching open PRs`, confirmed in its own stored `kinds` examples: 5 of 5 are `state: open`, and the sample IS #34). A closed PR simply stops appearing, and an incremental sync upserts but never reaps. **The ship loop therefore generates stale Port entities as a matter of course** — this is a lifecycle defect, not a one-off. Deleted manually; the durable answer is below.

**c. `POST /v1/integration/github-weyland/resync` does not work.** It returns `{"ok":true}` and then does nothing: no new log rows, `resyncState.lastResyncEnd` unchanged, entity count unchanged — **even with `incrementalSyncEnabled: false`**. Do not treat a 200 from that endpoint as evidence of anything. The stale entity had to be removed with `DELETE /v1/blueprints/githubPullRequest/entities/<id>`.

**d. The `incrementalSyncEnabled` override is not durable, and the row above had the polarity backwards.** It read `true` on 2026-08-23 despite having been PATCHed to `false` the night before — the integration is **Port-hosted SaaS** (`installationType: SaasOAuth2`, `integrationType: github-ocean`), so it re-registers and pushes its own `appSpec`, overwriting server-side changes (`updatedAt` moved to 09:45Z with no human action). More importantly the reasoning was inverted: with incremental **on**, `resyncState` showed **no full resync in 31 hours** despite `scheduledResyncInterval: 4h` — the scheduled resync becomes incremental, so the reaper never runs and closed PRs accumulate permanently. **Set to `false` deliberately on 2026-08-23** so scheduled resyncs are full and self-healing.

The stated rationale for restoring it does not survive measurement: it cited GitHub's **search API** 30/min limit, but the PR path is `GET /repos/{owner}/{repo}/pulls` with REST pagination (per the integration's own log), and a full resync measured **5 seconds** across six repos. Six full resyncs a day is not a rate-limit concern.

> **Open verification, 2026-08-23:** confirm that with the flag `false` a scheduled resync actually runs FULL — `resyncState.lastResyncEnd` should advance past `2026-08-22T05:29:30Z` within one 4h window of `lastSyncedAt: 2026-08-23T13:16:11Z`. If it does not, scheduled resyncs are broken the same way `POST /resync` is, and stale-entity reaping has **no** working trigger at all — which would make a periodic `DELETE`-based reconciler the only option.

**e. A NEW recurring failure source, caused by enabling `nightly-images`.** `GET /v1/audit-log?status=FAILURE` now returns **176 of 200 rows for a single identifier**: `--woodpecker-weyland-cluster`. The failing entity is a `k8s_pod` (`wp-01m0pfve8a22w7fgbvnn2ck5pe-woodpecker-weyland-cluster`) whose `k8s_workload` relation resolves with **empty owner-name and empty owner-kind** — Woodpecker's kubernetes backend creates pipeline step pods as **bare pods with no `ownerReferences`**, and the `v1/pods` mapping assumes every pod has an owner. All 176 landed at **05:01:38Z, the nightly-images run**. This will recur every night and on every manual pipeline.

Fix belongs with the `weyland-cluster` codification: make the `k8s_workload` relation conditional on `ownerReferences` being present rather than string-concatenating empties, or exclude the `woodpecker` namespace from the pod selector. The first is correct; the second is a workaround.

**The jobs/cronjobs fix DID hold** — no Job-owned pod failures remain, and the jupyterhub/tool-server `k8s_replicaSet` residue is down from ~36 to **19**. That residue is still unexplained and still not chased.

**Ordering:** this runs **after** the B131/B135 ship-loop work closes — same workstream, but that work is mid-flight and this would fragment it.

**Residual, not chased:** ~36 failures pointed at missing `k8s_replicaSet` entities for jupyterhub's `hub` and `proxy`. Those replicasets pass the mapping's namespace selector yet are not ingested — separate and unexplained.

**Diagnostic note for whoever does this work:** the authoritative sources are `GET /v1/integration/<id>/logs` (the integration's own resync log, showing raw-result counts per kind) and `GET /v1/integration/<id>/kinds` (stored raw payload examples). Both are readable via the API and both answer questions the repo cannot. Three live config changes were made here on guesses before those endpoints were consulted; two were solving a non-problem.

Linear: EMA-198. Relates **B131** (its Port surface is what exposed this), **B135** (same ship-loop workstream), B60 (the split this restores), EMA-172 (DORA deployment events), B133 (the scan whose wrong conclusion led here).

# Completeness / Gap Audit — 2026-06-26

Multi-agent audit (9 domain auditors + synthesis) of the weyland platform for **completeness gaps** —
artifacts that "run once" but aren't operationally complete. Graded each against 5 gap types:
**trigger · lineage · gitops (reproducibility) · monitoring · docs**, and cross-checked the backlog's
"✅ done" claims. 56 raw gaps → 42 deduped.

- **data-mesh-now: 14** (8 high / 4 medium / 2 low) — solved as part of B1 (this register's top section).
- **platform-later: 28** (9 high / 14 medium / 5 low) — **B69**, cleared immediately after B1.

---

## DATA-MESH — SOLVE NOW (bucket = data-mesh-now) — ✅ RESOLVED 2026-06-26

All 14 closed inline with B1: iceberg trigger wired (`weyland_eval_score_job`); all schedules
`default_status=RUNNING`; `iceberg_publish` env hardened; Dagster→Iceberg lineage edge emitted
(verified end-to-end); recipes codified (`k8s/data-mesh/datahub-ingestion/`); MinIO + Postgres
backups to NVMe (CronJobs, tested green); ServiceMonitors/PodMonitor + down-alerts; Loki rule
broadened to `data-mesh`; Dagster freshness watchdog (`k8s/dagster/freshness.yaml`, external —
the run_status_sensor is dead on 1.13); secrets runbook + lakeFS encrypt-key escrow
(`docs/runbooks/data-mesh-secrets.md`); storage→DataHub assessed (s3 for aidlc-kb only, rest
redundant/no-connector); docs corrected. **Deferred to B69 (cross-cutting):** the full
SealedSecrets/External-Secrets mechanism for all imperative secrets.



### High
- **[trigger] `iceberg_eval_scores` orphaned from every job & schedule** — `assets/iceberg_export.py` (group "eval") + `schedules/__init__.py` (eval jobs select named assets only; ingestion subtracts group "eval") — Fix: add `iceberg_eval_scores` to `weyland_eval_score_job`'s selection (`AssetSelection.assets("eval_scores","iceberg_eval_scores")`).
- **[lineage] Dagster→Iceberg→DataHub hop broken; tables never cataloged** — `datahub_emit.py` (PLATFORM="dagster" only), `iceberg_publish.py`, `k8s/data-mesh/datahub-values.yaml` (no Iceberg/Nessie source) — Fix: add a git-tracked DataHub Iceberg ingestion recipe → `nessie.data-mesh.svc:19120/iceberg`, and emit a cross-platform `UpstreamLineage` edge from each `iceberg_*` dagster URN to its `platform=iceberg` dataset URN.
- **[gitops] All Dagster schedules default to STOPPED** — `schedules/__init__.py`, `definitions.py` (no `default_status`) — Fix: `default_status=DefaultScheduleStatus.RUNNING` on every `ScheduleDefinition` (also fixes `datahub_catalog_emit_schedule` + B62 `ai_session_schedule`).
- **[gitops] Grafana DataHub source is UI-only with an imperatively-minted SA token** — no recipe/secret in git (`backlog.md:835/838`) — Fix: codify as a managed-ingestion recipe under `k8s/data-mesh/` + store the Grafana SA token via SealedSecrets/External Secrets.
- **[gitops] Data-mesh & catalog secrets are imperative one-offs; lakeFS encrypt-key un-escrowed** — `k8s/dagster/user-code.yaml` (`datahub-token`, `iceberg-s3-secret`), `datahub-values.yaml` (`datahub-auth-secrets`, `datahub-oidc`), `minio-creds` — Fix: SealedSecrets/SOPS for all; **escrow lakeFS `AUTH_ENCRYPT_SECRET_KEY`** (losing it bricks all stored creds); `iceberg_publish.py` `os.environ[...]` hard-index → KeyError on rebuild.
- **[other] MinIO data products on a single un-backed-up USB disk** — `k8s/minio/pv.yaml` (static local PV, no RAID); `storage-minio.md` declines backup but none exists — Fix: scheduled `mc mirror` CronJob of warehouse+lakefs (+aidlc-kb, mlflow) to a second target; correct the "reproducible" runbook claim.
- **[other] Nessie & lakeFS Postgres metadata (commit history / branch refs) have no backup** — `nessie.yaml`, `lakefs.yaml` — Fix: scheduled `pg_dump` CronJob (meshed for STRICT Postgres) → MinIO backup bucket, with rotation.
- **[monitoring] No Prometheus/Alertmanager for Nessie or lakeFS; MinIO ServiceMonitor not in git** — zero ServiceMonitor/PrometheusRule in `k8s/data-mesh/` — Fix: ServiceMonitors (Nessie :9000 `/q/metrics`, lakeFS :8000 `/metrics`) + pod-down/health alerts, commit the MinIO ServiceMonitor, Kuma checks on in-cluster health endpoints.

### Medium
- **[lineage] Storage tier (lakeFS repos, MinIO buckets) not ingested into DataHub** — Fix: add s3 source for warehouse/lakefs buckets + a lakeFS source via the meshed executor.
- **[lineage] No column schema on the tabular Iceberg data products** — `datahub_emit.py:10-11` stale "not tabular" comment — Fix: emit `SchemaMetadata` for `iceberg_*` datasets from the Arrow/Iceberg schema; fix the comment.
- **[monitoring] No failure/freshness monitoring on catalog-emit, Iceberg export, or DataHub executor** — Fix: Dagster run-failure sensor → GlitchTip/Telegram, Kuma heartbeat on the hourly emit, freshness check on `iceberg_*`; MinIO/Nessie/lakeFS down alerts.
- **[monitoring] Loki log-spike alert scoped to `namespace="weyland"` only** — `k8s/loki/loki-rules-configmap.yaml` — Fix: broaden the LogQL selector to cover `data-mesh`.

### Low
- **[docs] Backlog marks the Grafana catalog source ✅ DONE though non-reproducible** — `backlog.md:835` — Fix: downgrade to "configured (UI-only, not yet GitOps)".
- **[docs] DataHub emitter dataset count stale (15 vs 17)** — `backlog.md:849-851` — Fix: update to 17.

---

## PLATFORM-WIDE — clear right after B1 (bucket = platform-later, → B69)

### High
- **[gitops] No secrets-management mechanism; ~25 cluster secrets are imperative-only** — `neo4j-secret`, `tool-server-sentry`, `weyland-alerts-telegram`, grafana-admin/oauth, all SSO client secrets — Fix: adopt External Secrets/SealedSecrets/SOPS, or minimally commit a `*-secret.example.yaml` per secret + `docs/runbooks/secrets.md` index (name→keys→regen).
- **[monitoring] Ollama (sole generation backend) has no Prometheus/Alertmanager coverage** **(RESOLVED B79 — moved to rogueone GPU)** — CT 102 `192.168.1.244:11434` — Fix: Kuma HTTP monitor on `/api/tags` (Telegram) + blackbox probe + PrometheusRule.
- **[monitoring] Hermes gateway has zero failure monitoring** — `uptime-kuma.md:27` — Fix: Kuma push heartbeat from a CT 104 systemd timer gated on `systemctl is-active hermes-gateway`.
- **[gitops] Hermes agent runtime not reproducible from git** — `hermes.tf` is CT shell only — Fix: versioned bootstrap script under `nodes/weyland/hermes/` (config.yaml + mcp_servers + pinned `python-telegram-bot[webhooks]==22.6` + kanban init + templated `.env`).
- **[gitops] tool-server MCP image (`weyland-tool-server:local`) not reconstructible** — `imagePullPolicy: Never`, hand-built → ErrImageNeverPull on rebuild → `/mcp`+`/mcp-act` never start — Fix: push to `registry.weyland.lab` (**now exists, B-RT** — the local-registry fix is unblocked) / Woodpecker pipeline / committed bootstrap. (Still open: the tool-server image itself hasn't been migrated off `:local`/`Never` yet.)
- **[gitops] Always-firing `telegram-test` alert committed & Argo-synced** — `k8s/monitoring/telegram-test-rule.yaml` (`expr: vector(1)`) → pages every 4h forever — Fix: delete from git or add to `monitoring-extras` exclude.
- **[gitops] Uptime Kuma monitor definitions live only in SQLite on a PVC** — 23 monitors built in UI — Fix: export Kuma Backup JSON into the repo, or migrate critical checks to git-managed blackbox Probe CRDs.
- **[monitoring] No dead-man's-switch — Watchdog routed to `null`** — `kube-prometheus-stack-values.yaml` — Fix: route Watchdog to an external heartbeat (healthchecks.io / Kuma push).
- **[gitops] Entire `k8s/istio/` set (incl. STRICT mTLS PeerAuthentication) not onboarded to Argo** — 8 manifests in 0 Applications — Fix: add an Argo Application for `k8s/istio/` (ServerSideApply for CRD-bearing objects).

### Medium
- **[gitops] Ollama runtime perf/OOM config not reproducible** — systemd drop-in + `num_thread 8` Modelfiles (~160x) only in the runbook — Fix: Proxmox hook_script/cloud-init bootstrap from `ollama.tf`.
- **[trigger] Eval harness on-demand only; leaderboard frozen at run 3 (2026-06-13)** — Fix: low-frequency (weekly) schedule or freshness check on `eval_runs.created_at`.
- **[trigger] `roadmap-sync` cron is an un-codified manual crontab** — `agent-hermes.md:391` — Fix: ship `hermes-roadmap-sync.service`+`.timer` in `nodes/weyland/hermes/`.
- **[gitops] ai_session producer runs from an uncommitted rogueone crontab** — `scripts/ai_session_feeder.py` — Fix: committed k8s CronJob or systemd timer + freshness alert.
- **[gitops] `ai_session` blueprint (B62) not codified in tofu** — Fix: `tofu import port_blueprint.ai_session`, strip phantom fields, update `opentofu.md` to 13.
- **[gitops] Port ingestion integrations + webhooks are imperative MCP/UI one-offs, unmonitored** — Fix: document exact recreate steps per integration + freshness alert per key blueprint.
- **[trigger] `docs.weyland.lab` rebuilds only on manual pod restart** — Fix: CronJob `rollout restart deploy/docs-site` + surface built commit/date.
- **[trigger] code-quality scans (semgrep, trivy) are one-shot Jobs, not scheduled/Argo** — Fix: weekly CronJobs, onboard the dir as an Argo Application, last-scan freshness signal.
- **[trigger] Woodpecker has no real build/test/deploy pipeline and no cron** — Fix: Woodpecker cron trigger, or land B57 CI→registry→git pipelines (B57's registry prerequisite is **now met** — `registry.weyland.lab`, B-RT); document no auto-trigger today.
- **[gitops] Loose `k8s/` root files not reconciled by Argo** — `coredns-custom.yaml` (load-bearing), `coredns-lan.yaml`, `rbac-default-sa-noautomount.yaml`, headlamp trio in 0 Applications — Fix: add Applications or widen `loose-apps` globs.
- **[monitoring] LGTM stack does not monitor itself** — no ServiceMonitor on loki/tempo/alloy — Fix: enable `monitoring.serviceMonitor` + `LokiDown`/`AlloyDaemonSetNotReady` rules.
- **[monitoring] traefik-forward-auth is a single-replica SPOF with no probes** — gates ~18 UIs — Fix: liveness+readiness on :4181 + synthetic monitor on `auth.weyland.lab/_oauth` + Keycloak `/health/ready`.
- **[docs] Live `dashboard.weyland.lab` absent from hosts.md/api.md/arch** — Fix: add host + UI-table rows + runbook section.
- **[gitops] OpenClaw degraded/unreproducible but listed ✅ healthy** **(OBSOLETE B28 — OpenClaw dropped 2026-07-17)** — `hosts.md:13` — Fix: flag degraded/deprioritized (or retire + tear down vm-100); codify compose if kept.

### Low
- **[gitops] LiteLLM pinned to mutable `main-stable` under selfHeal** — Fix: pin to immutable tag/digest.
- **[gitops] `k8s_workload` relation target not codified; bare apply to empty org fails** — `tofu/port/catalog.tf:393-399` — Fix: stub a minimal blueprint or document exporter-first ordering.
- **[docs] Backlog B59 overclaims component→k8s_workload entity links "codified in tofu"** — Fix: correct to "intentionally NOT codified".
- **[docs] Backlog B58 claims 28 Argo apps; actual 37** — Fix: update count.
- **[docs] MinIO console (`minio.weyland.lab`) left out of the forward-auth SSO sweep** — `k8s/minio/ingress.yaml` — Fix: add the forward-auth middleware or delete the dead console ingress.

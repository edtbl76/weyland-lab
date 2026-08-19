# Completeness / Gap Audit — 2026-06-26

Multi-agent audit (9 domain auditors + synthesis) of the weyland platform for **completeness gaps** —
artifacts that "run once" but aren't operationally complete. Graded each against 5 gap types:
**trigger · lineage · gitops (reproducibility) · monitoring · docs**, and cross-checked the backlog's
"✅ done" claims. 56 raw gaps → 42 deduped.

- **data-mesh-now: 14** (8 high / 4 medium / 2 low) — solved as part of B1 (this register's top section).
- **platform-later: 28** (9 high / 14 medium / 5 low) — **B69**, cleared immediately after B1.

---

## B69 CURRENT REGISTER — re-audit 2026-07-17 (supersedes the 2026-06-26 snapshot below)

Fresh 3-agent sweep (secrets+gitops · monitoring · backup/trigger/docs) graded against the DoD **operational-completeness** pillar (reproducible · secret-restorable · monitored · backed-up · triggered). The 2026-06-26 register below is kept for history; several items are now RESOLVED (data-mesh backups, all schedules `RUNNING`, Kuma backup committed, Grafana recipe codified) or OBSOLETE (Ollama→rogueone B79, OpenClaw dropped). Current open gaps, prioritized into waves:

> **▶ RE-VERIFIED 2026-07-20** — every Wave 1/4/5 item re-checked against git AND the live cluster. Result: the
> register had drifted **in both directions**. Now-CLOSED (see per-wave ✅ marks below): data-mesh alert loading,
> `telegram-test`, cube plaintext key, backup coverage, Argo onboarding, code-quality/sonar schedules, SPOF probes,
> dead-man's-switch, and the whole 07-18 "still uncommitted" push list.
>
> **The instructive miss:** the "data-mesh alerts silently dead" item — flagged here as the single biggest live risk —
> was fixed by setting `ruleSelectorNilUsesHelmValues: false` **once**, NOT by the prescribed "add `release: monitoring`
> to 17 files". All 14 rule files still lack that label and load fine (52 PrometheusRules live). Following the register
> literally would have meant 17 pointless edits; trusting its status would have meant believing data-mesh alerting was
> dead when it isn't. A stale register is worse than none precisely because it is specific.
>
> **STILL OPEN after this pass:** ~~LGTM self-monitoring~~ (✅ done 2026-07-20) · ~~Hermes heartbeat~~ (⏸ gated on B66 — Hermes is off) · 2 uncodified triggers (docs-site rebuild, eval
> harness/leaderboard, roadmap-sync `.timer`, ai_session producer crontab — 7 CronJobs live, none of these) · GitOps
> misc (n8n workflows→git, LiteLLM `main-stable`→digest, DataHub recipes UI→reconciled) · Wave 5 docs-drift (Argo app
> count drifted again: backlog says 48, live is **59** / 58 in git) · ~~`weyland-image-prune.timer`~~ (✅ installed 2026-07-20, next Sun 15:09 UTC) · delete CT-102 + `hosts.md` cleanup · Prometheus/Loki retention caps.
> Disk pressure is NOT a concern anymore: `/` 63%, `/mnt/minio` 9%.

> **▶ AM PICKUP — 2026-07-18** (historical; the PUSH list below is now fully committed).
>
> **DONE:** drift cleanup — every Argo app back to **Synced/zero-drift**; `b69-onboarding.yaml` deleted, its 9 apps redistributed to `loose-apps`/`subdir-apps`/`helm-apps` (no batch-named files); dedup'd the double-owned `data-mesh/traefik-forward-auth` Middleware (dropped from cube.yaml) + `minio/minio` ServiceMonitor (dropped from data-mesh); targeted `ignoreDifferences` for the CRD `preserveUnknownFields`+printer-column `priority` (gatekeeper/flink), STS `volumeClaimTemplates` (opensearch/datahub-prereq), and datahub-gms-secret. Deleted the **live `qdrant-fault-demo` VirtualService** (a fault-injector still adding 3s latency to qdrant). **Wave 4 Slice 1** (SPOF probes: traefik-forward-auth tcpSocket, cube `/livez`+`/readyz`, n8n `/healthz`) + **Slice 2** (blackbox synthetic monitoring for the 16 uncovered hosts + `WeylandEndpointDown` alert — verified). **DNS OUTAGE fully fixed** — weyland-lan-dns `hostPort:53` via k3s ServiceLB captured the node's own `127.0.0.53` resolver → node DNS black-holed on pod death → cascade; fix = `hostPort` pinned to `hostIP: 192.168.1.243` + Service `ClusterIP` (no svclb) + a systemd-resolved drop-in so mother resolves weyland.lab via LAN DNS while external stays on the router. **mother disk +400G** (92% → 61%). node-disk alert + image-prune timer authored.
>
> **PUSH (still uncommitted):** `nodes/mother/host/systemd/resolved.conf.d/weyland-lab.conf`, `nodes/mother/host/systemd/weyland-image-prune.{service,timer}`, `k8s/monitoring/node-disk-alerts.yaml`, `docs/runbooks/lan-dns.md`, `docs/schedules.md`. (The node-disk alert is the priority — Argo syncs it → early-warning live.)
>
> **TODO (AM):** install the prune timer (rsync + `systemctl enable --now`); move **minio-backup (51G) → `/mnt/minio`**; **de-Argo + drop the spent musicbrainz-dbdump (25G)**; **Prometheus/Loki retention caps**; **delete CT-102 (ollama)** + clean rogueone `/etc/hosts` (`.244` stale) + hosts.md "decommissioned"→"deleted"; finish **Wave 4** (code-quality CronJobs, Hermes heartbeat, LGTM self-monitoring).

### Wave 1 — quick high-value fixes (small edits, real safety) — ✅ ALL DONE (verified 2026-07-20)
- ✅ **RESOLVED DIFFERENTLY** — `ruleSelectorNilUsesHelmValues: false` in `kube-prometheus-stack-values.yaml` makes the
  operator load rules regardless of label; 52 PrometheusRules live. The label fix below was never needed.
  **[monitoring] data-mesh alert rules NOT loaded** — all 17 `k8s/data-mesh/*.yaml` PrometheusRules are labeled `app:` not `release: monitoring`, and the stack sets no `ruleSelectorNilUsesHelmValues: false`. Every data-mesh down-alert (Nessie/lakeFS/DataHub/MinIO/Trino/GizmoSQL/Feast/Superset/all 10 Tier-2) is **silently dead**. Fix: add `release: monitoring` to each (or set the selector). Confirm live: `kubectl get prometheusrule -A -l release=monitoring`.
- ✅ **DONE** (Watchdog → `healthchecks-watchdog` webhook, `url_file` from the `watchdog-healthcheck` secret, `repeat_interval: 5m`). **[monitoring] no dead-man's-switch** — Alertmanager Watchdog → `receiver: 'null'`. Route to an external heartbeat (healthchecks.io / Kuma push) so a dead Prometheus/Alertmanager is noticed.
- ✅ **DONE** (sealed into `cube-secret` during SEC-1). **[secrets] cube JWT signing key in PLAINTEXT in git** — `k8s/cube/cube.yaml` (`CUBEJS_API_SECRET: weyland_cube_dev_secret`). Move to a sealed/imperative secret.
- ✅ **DONE** (file deleted from git). **[monitoring] `telegram-test` always-firing alert** — `k8s/monitoring/telegram-test-rule.yaml` (`expr: vector(1)`), self-healed by `monitoring-extras`; pages every 4h forever. Delete / exclude.
- ✅ **DONE** (`mlflow` + `tofu-state` added to the mc-mirror; `postgres-backup.yaml` full-instance `pg_dumpall`; both live). **[backup] extend the two backup CronJobs** — add `mlflow` + `tofu-state` (+`registry`) to `k8s/minio/backup.yaml` mc-mirror (IRREPLACEABLE: trained models, all IaC state); extend `k8s/data-mesh/backup.yaml` to `pg_dumpall` the FULL `weyland-postgres` (only nessie/lakefs of its 12 DBs are dumped — keycloak realm/superset/weyland-core are irreplaceable and unbacked).
- ✅ **DONE** (`k8s/istio/` + `k8s/code-quality/` in `subdir-apps`; loose root files in `loose-apps`; 59 apps live). **[gitops] Argo-onboard the un-reconciled dirs** — `k8s/istio/` (8 manifests incl STRICT-mTLS PeerAuthentication), `k8s/code-quality/`, and the loose root files (`coredns-custom.yaml` = load-bearing LAN DNS, `coredns-lan.yaml`, `rbac-default-sa-noautomount`, headlamp trio, `rag-index-{neo4j,pgvector}.yaml`) — currently in 0 Applications.

### Wave 2 — secrets management (the big rock) — ✅ DONE 2026-07-17
- **[secrets] SealedSecrets adopted.** Bitnami controller (chart 2.19.1 / v0.37.0) in kube-system via the `sealed-secrets` Argo app; controller private key escrowed off-cluster. **53 imperative secrets sealed** into git (`k8s/sealed-secrets/sealed/<ns>__<name>.yaml`) via the explicit allow-list in `scripts/seal-secrets.sh`, applied by the `sealed-secrets-manifests` Argo app — each live secret adopted in place (ownerRef=SealedSecret, no disruption). Runbook `docs/runbooks/secrets.md` (mechanism: seal/restore/rotate/escrow); `data-mesh-secrets.md` re-pointed to it. Chart/operator-generated secrets (datahub-chart/superset/lightdash/jupyterhub-hub/kafka-prereq/prometheus-operator/webhook certs) deliberately NOT sealed (charts recreate them). Bricking values raw-escrowed: lakeFS `AUTH_ENCRYPT_SECRET_KEY`, n8n `N8N_ENCRYPTION_KEY`, glitchtip `SECRET_KEY`.
  - **Deferred (not blocking):** TLS/CA (`weyland-wildcard-tls` 45 ingresses + mkcert CA) left unsealed — mkcert-regenerable, replicated across ns, and they expire; revisit if a cert-manager is introduced.

### Wave 3 — reproducibility (images off `:local`) — ✅ DONE 2026-07-17
- **[gitops] `:local` / `imagePullPolicy: Never` images migrated.** 8 buildable images built+pushed to `registry.weyland.lab:v1` (`scripts/build-push-images.sh`, reusable, TAG-parameterized): weyland-tool-server · weyland-rag-index (×5 manifests) · weyland-dagster-base (×2) · weyland-dagster-user-code (×2) · weyland-flink (×3) · weyland-flink-py · feast-server (×2) · store-scaler. All 17 manifests repointed to `registry.weyland.lab/<name>:v1` + `Never`→`IfNotPresent`; `ranger` `Never`→`IfNotPresent` (real image, pullable). Verified: only musicbrainz on `:local`, no pull/crash errors. k3s nodes pull via node-level containerd auth (no imagePullSecret). Several deploys were already drifted to `:v1` live with git stale at `:local` (e.g. tool-server) — now reconciled.
  - **ROOT CAUSE found + fixed (the real work):** pushing multi-GB layers to `registry.weyland.lab` failed at exactly 60s (HTTP 499, registry never saw the blob). k3s **Traefik v3 default `readTimeout=60s`** bounds the full request-body read → large pushes guillotined. Fix: `k8s/traefik/traefik-config.yaml` (HelmChartConfig, `readTimeout: 0s`), Argo-managed (`traefik-config` app). See [[traefik-readtimeout-registry-push]].
  - **EXCEPTION (deliberate):** `musicbrainz-mb-import:local` left as-is — built from the external musicbrainz-docker repo (no in-repo Dockerfile), a completed one-off restore Job (only re-pulls on a manual re-run). Documented in the manifest.
  - **Deferred:** wire a Woodpecker/B57 auto-build pipeline (currently manual `build-push-images.sh` on rebuild).
- Note: the failing **`weyland` MCP** (`:30080/mcp`) is NOT an image problem — the tool-server pod is healthy on `:v1`. If the MCP still misbehaves in Claude Code it's the **client config** → moved to Wave 5 (MCP revisit).

### Wave 4 — monitoring / probes / triggers — PARTIALLY DONE (verified 2026-07-20)
- ✅ **MOSTLY DONE** — Slice-1 probes + a blackbox exporter covering **19** endpoints give synthetic coverage even where no ServiceMonitor exists (cube/jupyterhub/valkey/keycloak still have none). ❌ **STILL OPEN: LGTM self-monitoring** — no `LokiDown`/`TempoDown`/`AlloyDown` rules anywhere. **[monitoring] SPOFs unmonitored** — Keycloak + traefik-forward-auth (single replica, no probes, gate ~18 UIs) → liveness/readiness + down-alerts + Kuma synthetic. Cube/JupyterHub/Ranger/Valkey no ServiceMonitor/alert. Gatekeeper/Flink/Ray scrape-but-no-down-alert. LGTM doesn't monitor itself (no loki/tempo/alloy SM + Down rules).
- ⏸ **GATED ON B66 — not open.** Hermes is currently **shut off**; the agent lane is consolidated into **B66** (Operator Agent Platform), where the base-agent decision (Hermes vs OpenClaw) is made. Monitoring a deliberately-stopped service would page forever, so the heartbeat units are **staged in git, not installed**: `nodes/weyland/hermes/hermes-heartbeat.{service,timer}` (push-based — CT 104 is outside k3s so Prometheus has no scrape path; gated on `systemctl is-active` so a dead gateway can't report healthy). Install alongside a Kuma Push monitor when B66 brings an agent back up. **[monitoring] Hermes gateway** (CT 104) no failure monitoring → systemd heartbeat gated on `systemctl is-active` → Kuma push.
- ⚠️ **PARTIAL** — ✅ code-quality scans done (`code-scan-suite` Sun 13:00 + `sonar-scan` Sun 12:00, both live). ✅ roadmap-sync `.timer` authored 2026-07-20 (`nodes/weyland/hermes/roadmap-sync.{service,timer}`, daily 06:30, Persistent — staged with the Hermes units). ✅ docs-site rebuild codified 2026-07-20 (`k8s/docs-site/docs-site-rebuild.yaml` — daily 05:30 NY `rollout restart`, least-privilege SA pinned to that one Deployment via `resourceNames`). ✅ eval harness/leaderboard scheduled 2026-07-20 (`weyland_eval_schedule` Sat 03:00 + `weyland_eval_score_schedule` Sat 05:00, both `STOPPED` pending a green manual run — Ollama moved to rogueone in B79). ✅ ai_session producer codified 2026-07-20 (`nodes/rogueone/systemd/ai-session-producer.{service,timer}` — user unit, needs `loginctl enable-linger`). **Wave 4 triggers COMPLETE.** (7 CronJobs live, none of these). **[trigger] manual-only → schedule + freshness** — docs-site rebuild (CronJob), code-quality scans (weekly CronJob + Argo), eval harness/leaderboard (weekly or freshness), roadmap-sync (`.timer`), ai_session producer (commit the rogueone crontab).
- **[gitops] reproducibility misc** — Hermes runtime bootstrap, Ollama perf/Modelfile config, LiteLLM mutable `main-stable`→digest, headlamp Helm→Argo Application, n8n workflows→git, DataHub recipes UI→reconciled.

### Wave 5 — docs-drift
- Argo app count 28→**48** (backlog); strike Backstage/Jaeger/OpenClaw from the backlog BODY (retired/dropped, still referenced as live); reconcile DataHub dataset counts (3255 vs 3282 vs 3256); MinIO console SSO sweep.
- **Refresh `docs/platform-map.html`** — the hand-authored visual map has drifted from the live component set (openclaw card removed 2026-07-17; likely more ghosts/omissions — e.g. the full B1 data-mesh, LikeC4). Audit it card-by-card against `hosts.md` + the LikeC4 model and reconcile. (Now a standing DoD item — see [[completion-criteria]] pillar 1.)
- **Audit the Port.io catalog for drift** — reconcile what Port CLAIMS is integrated vs live reality (a standing DoD item now, pillar 1). Live evidence: the backlog/arch present the **K8s exporter (`weyland-cluster`) as a live integration**, but no in-cluster exporter is deployed — the `k8s_workload` links are MCP-maintained. Resolve it: either deploy the exporter (outbound, LAN-OK) or correct the claim + own the MCP-maintained model. Also **revisit the failing `port` MCP here** (`npx mcp-remote https://mcp.port.io/v1` re-prompts OAuth every session and currently fails to connect — remove it from the Claude Code config, or fix token persistence).

**Biggest live risks:** unloaded data-mesh alerts (believed-working, dead) · no dead-man's-switch · irreplaceable stores unbacked (core Postgres, mlflow models, tofu-state) · ~45 unmanaged secrets (one node loss = unrecoverable). Wave 1 removes most of the *immediate* danger cheaply.

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
- **✅ RESOLVED 2026-08-18 (B57a) — weyland-image CI→registry→git pipeline landed.** The weyland-lab `.woodpecker.yml`
  now builds the weyland-built images (via a persistent `buildkitd` Deployment) → pushes `git-<sha>` to
  `registry.weyland.lab` → opens a tag-bump PR → merge → Argo deploys, on a **nightly 01:00 NY cron** + manual
  (the LAN-webhook wall means cron/manual, not push — accepted). Validated live (store-scaler → `git-ec59b430`).
  Residual: build-status → Port (`ci_pipeline`) — **✅ RESOLVED 2026-08-19 (B63):** a `notify-port` step feeds the
  `weyland_ci_reliability` dashboard (both farms, both outcomes proven). See `runbooks/woodpecker.md`.
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

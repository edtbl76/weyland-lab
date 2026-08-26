# Weyland — Master Schedule

Single source of truth for **everything that runs on a timer** in the lab: Dagster schedules,
DataHub managed-ingestion sources, k8s CronJobs, **node systemd timers** (mother + rogueone), and **Woodpecker crons**.
Keep this updated whenever a schedule is added, moved, or disabled (same discipline as [hosts.md](hosts.md) /
[api.md](api.md); it's a DoD close-out check).

## Timezone — one clock now

As of **2026-07-02**, all timed systems are pinned to **America/New_York**, so what you read in any
UI is what actually runs — no mental TZ conversion:

| System | Timezone | How it's set |
|---|---|---|
| **Dagster** | America/New_York | `execution_timezone="America/New_York"` on every `ScheduleDefinition`. |
| **DataHub** managed ingestion | America/New_York | TZ selector per source in the ingestion UI. |
| **k8s CronJob** (scale-down) | UTC by convention → set `.spec.timeZone` | k8s CronJobs default to the kube-controller-manager's TZ; set `spec.timeZone: America/New_York` explicitly. |
| **Woodpecker cron** | **UTC** (NOT NY-pinned) | `repo cron add --schedule` is parsed in the server's clock = **UTC**; unlike Dagster/DataHub these do **not** auto-follow NY DST. Choose the UTC expression so the NY-equivalent stays inside the 00:00–06:00 window year-round (e.g. `0 5 * * *` = 01:00 EDT / 00:00 EST — both off-hours). |

> **History:** before the pin, Dagster schedules ran in **UTC** while DataHub ran in EDT — a `12 am`
> DataHub source was really `04:00 UTC`, colliding with Dagster's `ai_session`. The pin removed that trap.

## Master timetable (America/New_York)

Heavy = embeds/writes or large scans (guard the node's RAM). Light = metadata/read-only.

| Time (NY) | System | Job / source | Cadence | Weight |
|---|---|---|---|---|
| **02:00** | k8s CronJob | `data-mesh-scaledown` → cockroachdb/mongodb/mysql/gizmosql to 0 | daily | — (frees RAM) |
| **02:17** | Dagster | `weyland_ingestion_job` (RAG fan-out, serialized) | daily | **HEAVY** |
| — | Dagster | `ai_session` | **OFF — deliberately disabled** (was every 4h). Turned off on purpose; the B62 product does not auto-refresh and the rogueone producer keeps mirroring to MinIO in the meantime. **Not a fault — do not re-enable or alert on it without a decision.** If revived: run `weyland_ai_session_job` manually first (never passed as a job), then add it to the B94 watchdog. | light |
| **00:05** | Dagster | `feast_materialize_job` (Feast OFFLINE Postgres → ONLINE Valkey; **B140**). Uses an **explicit** `feast materialize <start> <end>` window, never `materialize-incremental`: `feast_metadata` carried a watermark of 2026-07-08 while every source event timestamp predates it (`track_audio_features` 2020-01-01, `state_health_risk` 2011→2024), so the incremental window was permanently empty — each run "succeeded", wrote nothing, printed no progress bar, and left the next run equally empty. The online store sat empty with feast-server green on its `/health` probe. The op **verifies its own work**: it samples a real entity key from the offline table and fails unless the online store serves a NON-NULL value (`statuses: PRESENT` is not evidence — Feast returns PRESENT with a null value for never-materialized keys). Slotted at 00:05: inside the pre-dawn window and clear of 00:20 `timeseries`. | daily | **light** — 89,741 + 770 rows, seconds |
| **00:20** | Dagster | `timeseries` (→ TimescaleDB hypertables) | daily (**overnight-only** — was every 4h) | med |
| **00:35** | Dagster | `datahub_catalog_emit` (custom emitters) | daily (**overnight-only** — was every 6h) | light |
| **00:50** | Dagster | `catalog` (model lookup) | daily (**overnight-only** — was every 6h) | light |
| 03:00 | Dagster | `datasets_music_land` | daily — **RUNNING** (enabled in the UI; code `default_status` is STOPPED, which only applies at first registration) | light in practice — assets **self-skip if fresh** (30-day window), so the ~342 MB FMA download is rare, not daily |
| 04:00 | Dagster | `datasets_health_land` | daily — **RUNNING** (as above) | light in practice — self-skips if fresh (7-day window) |
| **06:00** | Dagster | `weyland_dbt_job` (dbt build → 7 marts + tests; then publishes `manifest.json`+`catalog.json` to `s3://warehouse/_dbt_artifacts/`) | **weekly (Sun)** | **HEAVY** — Trino aggregations (4G heap; `approx_distinct`/`threads:2` guard the OOM) |
| 01:00 | DataHub | Grafana | daily | light |
| 01:15 | DataHub | Iceberg (Nessie) | daily | light |
| 01:30 | DataHub | MLflow | daily | light |
| 01:45 | DataHub | Superset | daily | light |
| 02:15 | DataHub | Kafka (Redpanda `datasets.*` topics + Avro schemas) | daily | light — metadata scan, no profiling |
| `0 */6 * * *` | k8s CronJob | `lancedb-sync` (mc mirror lakeFS Lance tables → viewer PVC) | every 6h | light — in practice the **PRIMARY** path, not a backstop. `lancedb_sync_sensor` watches `datasets_{music,health}_lancedb_load`, which live in the `datasets_*_stores` groups — **hydration is deliberately ON-DEMAND** (the hydrate jobs have no schedule), so the sensor idles for weeks by design and skips cleanly. A long-idle `lancedb_sync_sensor` is EXPECTED, not a fault. |
| **02:45** | k8s CronJob | `servicemonitor-coverage` (B148 observability — reconciles every live ServiceMonitor across **three planes**: `intended` (`.spec.replicas` on the workload it monitors), `actual` (`.status.readyReplicas`) and `observed` (its Prometheus scrape-pool target count). Any disagreement is a defect — `blind` (running and unmonitored), `down`, `zombie` (awake while declared parked), `stale`, `orphan`. **Exists because `data-mesh/trino` exported zero metrics for 59 days** behind one absent `metadata.labels` block on its Service, and the condition has no positive signal: `kubectl get servicemonitor` said 60d, `up{job="trino"}` returned no data, the Grafana panel looked idle. Reading `intended` from the cluster is sound **only because Argo selfHeal** (75 of 78 apps) overwrites `.spec.replicas` from git, making it a cached read of git rather than self-graded cluster state. Runs **unmeshed** — both targets (the API server, the Prometheus ClusterIP) have no sidecar. Logic is the byte-identical `scripts/check-servicemonitor-coverage.sh` embedded in the `servicemonitor-coverage-logic` ConfigMap, with a bats case asserting no drift; `scripts/tests/servicemonitor-coverage.bats` (30 cases) runs in CI. `spec.timeZone: America/New_York`. | daily | **light** — four k8s API GETs + one Prometheus GET, ~2s; 32Mi/25m requests. Slotted at 02:45 because **every 15-minute slot from 04:00 to 06:00 is taken** (04:00 `datasets_health_land` · 04:15/04:30/04:45 DataHub weekly scans · 04:30 `cron-freshness-check` · 05:00 dbt scan · 05:15 `port-pr-reconcile` · 05:30 `docs-site-rebuild` · 05:45 `pr-staleness-check` · 06:00 `weyland_dbt_job`). 02:45 is genuinely free with 15 min clear either side (02:30 `minio-backup`, 03:00 DataHub Neo4j) and sits **inside** the Design Rule #5 pre-dawn window, so it needs no carve-out. Chosen by reading the whole table rather than the neighbouring rows — the documented mistake that first put `port-pr-reconcile` on top of the 05:00 dbt scan. |
| **04:30** | k8s CronJob | `cron-freshness-check` (B135 observability — asks the **Woodpecker API** whether the `nightly-images` cron is `enabled` and whether `next_exec` has gone stale, and POSTs a synthetic `ScheduledWorkNotRunning` alert to Alertmanager v2). **Exists because a Woodpecker cron is not a Kubernetes object**: no CronJob, no Job, no pod, so kube-state-metrics cannot see it and no `kube_cronjob_*` metric ever will — which is why `nightly-images` sat `enabled:false` for four days unnoticed. Decision logic lives in the `cron-freshness-logic` ConfigMap so `scripts/tests/cron-freshness.bats` runs the same text the cluster does. `spec.timeZone: America/New_York`. Sibling `PrometheusRule` `cron-freshness` (k8s/monitoring/cron-freshness-rules.yaml) covers the ten **k8s** CronJobs with per-cadence freshness budgets. | daily | **light** — one Woodpecker API call + jq, ~2s; 32Mi/25m requests. Slotted at 04:30 because it is 3.5h after the 01:00 `nightly-images` cron (a genuine run has long finished) and clear of 05:30 `docs-site-rebuild` / 05:45 `pr-staleness-check` — stacking two watchdogs on one minute means one failure mode hides the other in the job log. |
| **05:15** | k8s CronJob | `port-pr-reconcile` (B144 — reaps Port `githubPullRequest` entities whose PR is no longer open. The `github-weyland` Ocean integration fetches **only open PRs**, so a closed PR stops appearing in the source data and an incremental sync upserts but never deletes — the entity survives forever claiming `status: open`. The B135 ship loop makes that a steady producer, not a one-off. **The only job in `pr-lifecycle/` that DESTROYS data**: it issues `DELETE /v1/blueprints/githubPullRequest/entities/<id>`, so every fetch fails CLOSED and `should_reap` is an allow-list matching `closed` alone — an empty or unrecognised state is never reaped. `PORT_REAP_DRY_RUN=1` reports without deleting. Decision logic lives in the `port-pr-reconcile-logic` ConfigMap so `scripts/tests/port-pr-reconcile.bats` runs the same text the cluster does. `spec.timeZone: America/New_York`. | daily | **light** — one Port call plus one GitHub call per open entity, seconds; 32Mi/25m requests. Slotted at 05:15 because **05:00 is the DataHub dbt scan** and 05:30 is `docs-site-rebuild` — 15 minutes clear on both sides, and it puts the three watchdogs at 04:30 / 05:15 / 05:45 without stacking any two on one minute. |
| **05:45** | k8s CronJob | `pr-staleness-check` (B131 — lists open PRs across the **six active repos** via the GitHub API, applies a per-kind age budget — 1 day for `ci/image-bump-*`, 7 days for everything else — and POSTs a synthetic alert to Alertmanager v2). Decision logic lives in the `pr-staleness-logic` ConfigMap so `scripts/tests/pr-staleness.bats` runs the same text the cluster does. `spec.timeZone: America/New_York`. | daily | **light** — one GitHub API call + jq, ~2s; 32Mi/25m requests. Slotted at 05:45 because 05:00 is the DataHub dbt scan, 05:30 is `docs-site-rebuild` and 06:00 is the weekly dbt build. **Daily, not `*/30`**: the alert auto-resolves after 5m and each firing is a NEW Alertmanager alert, so the CronJob cadence IS the Telegram rate — `*/30` would send ~48 messages a day per stale PR, and would violate Design Rule #5 (no mid-day auto-runs). |
| 03:00 | DataHub | Neo4j | daily | light |
| 03:15 | DataHub | Postgres (weyland core) | daily | med |
| **03:30** | DataHub | **CockroachDB** | weekly (Sun) | med |
| 03:45 | DataHub | MongoDB | weekly (Sun) | med |
| 04:15 | DataHub | Cassandra (datasets_music + datasets_health) | weekly (Sun) | med — profiling excl. lastfm |
| 04:30 | DataHub | ClickHouse (datasets_music + datasets_health) | weekly (Sun) | med — profiling cheap (columnar) |
| 04:45 | DataHub | Postgres — MusicBrainz | weekly (Sun) | **heavy scan** |
| 05:00 | DataHub | dbt (marts + tests-as-assertions + column lineage; reads `s3://warehouse/_dbt_artifacts/`, siblings onto `iceberg.dbt.*`) | daily | light — recommend 05:00 to clear the 01:00–04:45 DataHub train. Daily connector over **weekly** (Sun 06:00) artifacts = harmless idempotent re-ingest most days; fresh artifacts land ≤1 day after a build. |
| **08:00 (Sun)** | k8s CronJob | `sonar-scan` (SonarQube full analysis → the SonarQube server; clone + Flink-Java compile + sonar-scanner) | weekly (Sun) | med — Java build + scan (12:00 UTC) |
| **09:00 (Sun)** | k8s CronJob | `code-scan-suite` (the `quality-tools.yaml` roster — 19 scan-suite tools → Port + code-maat hotspots; one `scan-suite` image) | weekly (Sun) | **HEAVY** — semgrep auto + trivy fs (13:00 UTC) |
| **11:00 (Sun)** | node systemd (mother) | `weyland-image-prune` (`k3s crictl rmi --prune`) — frees ephemeral storage so the node never re-hits the eviction line (B69, `nodes/mother/host/systemd/`) | weekly (Sun) | — (host timer @ **15:00 UTC**; quiet slot clear of the DataHub train) · **INSTALLED 2026-07-20** (authored 07-18, enabled 07-20) |
| **05:30** | k8s CronJob | `docs-site-rebuild` — `kubectl rollout restart deploy/docs-site` (B69). docs-site rebuilds from a fresh `git clone` on every pod start, so without this the site silently serves a snapshot frozen at the last restart. No push-trigger available ([[lan-no-github-webhooks]]). | daily | light — restart only; the mkdocs build happens in the new pod's initContainer |
| **01:00** | Woodpecker cron | `nightly-images` (B57a — weyland image CI: detect changed images → BuildKit build+push `registry.weyland.lab/<img>:git-<sha>` → open a tag-bump PR; you merge → Argo deploys). Repo `edtbl76/weyland-lab`, `0 5 * * *` **UTC** = 01:00 EDT / 00:00 EST (see TZ note — Woodpecker crons are UTC, not NY-pinned). | daily | light most nights (BuildKit registry cache → only genuinely-changed images rebuild); **HEAVY** only on the one-time `:vN`→`git-<sha>` migration or many-change days. Placed at 01:00 to clear the **02:17 `weyland_ingestion` HEAVY** and the 02:00 scaledown; only overlaps the light 01:00 DataHub Grafana scan. The bump PR is merged **manually**, so nothing rolls unattended. **Dormant 2026-08-18 → 2026-08-22: the cron existed but was `enabled:false` and never fired; first real run is 2026-08-23.** |
| **22:30** | k8s CronJob | `minio-backup` (`mc mirror` MinIO → the backup target). **Carve-out to Design Rule #5 — see the note under the table.** `spec.timeZone: America/New_York` (added 2026-08-23; it previously had none and so ran in UTC). | daily | med — object-store mirror, I/O-bound |
| **23:00** | k8s CronJob | `pg-backup` (data-mesh — `pg_dump` of the **nessie + lakefs** Postgres). Same carve-out. `spec.timeZone` added 2026-08-23. | daily | med |
| **23:30** | k8s CronJob | `postgres-backup` (weyland core — `pg_dumpall`). Deliberately **30 min after** `pg-backup` so the two never overlap; both moved together on 2026-08-23 so the ordering is preserved. Same carve-out. `spec.timeZone` added 2026-08-23. | daily | med |
| **02:30** (+≤30m jitter) | node systemd (rogueone) | `restic-backup` (B130 — encrypted incremental restic → MinIO `rogueone-backup`: dotfiles + `~/.config` + `~/.claude` memory + secrets/keyring/mkcert + curated `~/Documents` + allow-listed repos' untracked-minus-bulk; reports Port `backup` entity + Kuma push heartbeat). `nodes/rogueone/{backup,systemd/restic-backup.*}` · **INSTALLED 2026-08-20** (user unit + `enable-linger`) | daily | light — ~415M deduped repo, incremental; runs on **rogueone** (not mother), so no single-node contention — only a light MinIO write |
| **Sat 03:00** | Dagster | `weyland_eval_job` (question-gen + run-matrix, RAG × 6 models) | weekly (Sat) — **STOPPED by default** | **HEAVY** |
| **Sat 05:00** | Dagster | `weyland_eval_score_job` (3-judge panel → `eval_leaderboard` + Iceberg publish) | weekly (Sat) — **STOPPED by default** | med |

> **Why Saturday, and why STOPPED:** Sunday is already full (dbt 06:00, sonar 08:00, scan-suite 09:00, prune 11:00)
> and 02:17 ingestion runs daily. Both eval schedules ship `STOPPED` (same posture as `soda_quality_schedule`)
> because **Ollama moved to rogueone in B79** and the eval path hasn't been exercised since — enable them in the
> Dagster UI only after a manual run comes back green.

**Staged but NOT installed** (they live in git; install when the gate clears):

| Unit | Where | Cadence | Gate |
|---|---|---|---|
| `ai-session-producer.{service,timer}` | **rogueone** (user unit) | every 4h at :07 | needs `systemctl --user enable --now` + **`loginctl enable-linger edwardmangini`**; replaces the uncommitted crontab |
| ~~`roadmap-sync.{service,timer}`~~ | ~~CT 104~~ | — | **RETIRED** — kanban → Linear (de-committed `9d9d982`); the B66 operator has no kanban-sync job |
| ~~`hermes-heartbeat.{service,timer}`~~ | ~~CT 104~~ | — | **RETIRED 2026-07-23** — Hermes destroyed |

> **⚠ rogueone GPU contention (affects the Sat eval runs).** rogueone has ONE GPU (RTX 5000 Ada Laptop, **16 GB**)
> and no usable iGPU, so it drives the desktop AND Ollama. A 30b model can starve the compositor and **hard-freeze
> the desktop** while Ollama keeps serving normally (no OOM/Xid/panic — it only looks broken from the keyboard).
> Guardrails: `nodes/rogueone/systemd/ollama-gpu-guardrails.conf` (max 1 loaded model, 30s keep-alive, 1.5 GiB
> reserved) — **validated 2026-07-20 under contention**: a full matrix + 3-judge scoring pass completed with the
> desktop in active use, no freeze. BIOS → Hybrid Graphics is the structural fix but is **deferred, not needed**.
> **B111 (2026-07-31):** the **vLLM on-demand bench** (`scripts/vllm-bench.sh`) is a THIRD VRAM contender (~8.8GB at
> `--gpu-memory-utilization 0.55`) — keep Ollama idle while a vLLM bench runs; it's on-demand so tear it down after.

**Ordering note (risk currently DORMANT):** a nightly `02:00` scale-down *would* take
cockroach/mongo/mysql/gizmosql to 0, and the DataHub ingestions that read them (Cockroach 03:30, Mongo
03:45, both **weekly Sun**) would then hit a scaled-to-zero store. **But the auto sleep/scale-down is
PARKED** — Argo `selfHeal` reverts `replicas:0` (see [runbooks/port-agent-easy-button.md](runbooks/port-agent-easy-button.md)
and [[store-scaler-easy-button]]). **KEDA was retired 2026-08-22** — it needs the SAME `/spec/replicas` carve-out, so it was never the unblocker. Stores stay up overnight, so 03:30/03:45 are
fine **today**. **When sleep is un-parked:** move the two affected weekly ingestions (Cockroach, Mongo) to
a **Sunday 01:xx** slot (before scale-down), or exclude those stores from the Sunday scale-down.
(MusicBrainz-Postgres and core-Postgres are NOT in the scale-down set, so 04:45 is fine for MusicBrainz.)

## The "easy button" — manual up, automatic down

- **Down is automated** (the `02:00` CronJob) → you *can't forget* to reclaim RAM.
- **Up is on-demand** via a Port self-service action per store (see below). First connection after a
  wake fails for ~10–30 s until the pod is Ready, then a retry connects.

Only `data-mesh` stores that are queried **rarely and ad-hoc** are in the set:
`cockroachdb`, `mongodb`, `mysql`, `gizmosql` (all `Deployment`, replicas 1, Recreate). Always-on
stores (core Postgres, Nessie, lakeFS, Trino, Valkey, TimescaleDB, MusicBrainz-Postgres) are **not**
scaled down — they back live services or the mesh.

> **Documented carve-out to Design Rule #5 — the three database/object backups (22:30 · 23:00 · 23:30 NY).**
> They sit just *outside* the 00:00–06:00 pre-dawn window, deliberately. Moving them in would put
> `minio-backup` at 02:30 NY — **13 minutes into the 02:17 HEAVY `weyland_ingestion_job`**, where
> `dagster-user-code` peaks at **10.6 Gi** on the same single node, and directly on top of `restic-backup`'s
> 02:30 slot. Late evening is quiet, off the working day, and clear of every heavy neighbour, which is what
> Rule #5 is actually protecting. Recorded here rather than left as drift.
>
> **How this was found (2026-08-23, B135 DoD sweep):** all three were **absent from this table** and none set
> `spec.timeZone`, so they ran in the controller-manager's clock (**UTC**) while their manifest comments claimed
> "02:30 / 03:00 local". They had been firing at 22:30/23:00/23:30 NY the whole time — confirmed against
> `kube_cronjob_status_last_successful_time` (02:32:49Z, 03:00:10Z, 03:43:33Z). The fix pinned each to
> `America/New_York` at the time it **already ran**, so nothing moved on the day and they stop drifting an hour
> in EST. A timer that runs but has no row is drift; so is a comment that describes a clock the timer isn't using.

## Design rules

1. **One clock** — everything in America/New_York. New timers inherit it explicitly. **Exception: Woodpecker crons run in UTC** (not NY-pinnable) — pick the UTC expression so the NY-equivalent stays inside the 00:00–06:00 off-hours window in **both** EDT and EST (see the TZ table).
2. **Spread the heavy stores** — Postgres-core, Cockroach, Mongo, MusicBrainz never share a 15-min slot.
3. **Static data → weekly, not daily** — Cockroach (brfss/nhis), the Mongo *datasets*, and MusicBrainz
   were loaded once; daily re-profiling just re-scans them. Weekly is enough.
4. **One node, one RAM pool** — Dagster runs execute *in* the user-code pod; DataHub ingestion in its
   executor; both draw on mother's ~32 GB. Staggering + scale-down are memory guards, not tidiness.
5. **NO mid-day auto-runs (2026-08-07, incident-driven)** — every Dagster schedule (and any new timer) runs
   ONLY in the pre-dawn window (~00:00–06:00 NY), never during the working day. **Mid-day is manual-only.** The
   single node can't absorb a scheduled job stacking on a manual/interactive load: an every-4h/6h cluster
   (`timeseries` 12:25 · `datahub_catalog_emit` 12:40 · `catalog` 12:50) firing at noon *on top of* a manual
   datasets-hydrate saturated mother (RAM 97% / CPU 105%, control plane unreachable). New periodic schedules are
   daily-overnight, not intraday. This rule is mirrored in the DoD.

## Change log

- 2026-08-23 — **Three backup CronJobs were undocumented AND running on the wrong clock.** `minio-backup`,
  `pg-backup` and `postgres-backup` had **no row in this table** and no `spec.timeZone`, so they ran in UTC
  while their manifests commented "local" — firing at 22:30/23:00/23:30 NY, not 02:30/03:00/03:30. Found by
  the B135 DoD timer reconciliation (a live-vs-doc diff, which is exactly what that check is for). Each is now
  pinned to `America/New_York` at the time it already ran — no same-day change, no EST drift — and each has a
  row above plus a written carve-out explaining why they stay outside the pre-dawn window. **Design Rule #1
  now has a guard it did not have:** "new timers inherit NY explicitly" was policy with nothing checking it.
- 2026-08-23 — **Added `cron-freshness-check`** (04:30 NY, B135) — the Woodpecker-cron watchdog. Slotted 3.5h
  after `nightly-images` (a genuine run has long finished) and clear of 05:30 `docs-site-rebuild` / 05:45
  `pr-staleness-check`; stacking two watchdogs on one minute means one failure mode hides the other.
- 2026-08-22 — **`nightly-images` was never actually running.** The Woodpecker cron (id 2, `0 5 * * *` UTC)
  was created **`enabled: false`** on 2026-08-18 and had never fired: `next_exec` was frozen at its first-ever
  slot (2026-08-19 01:00 EDT) and every pipeline on `edtbl76/weyland-lab` was `event: manual`. This table has
  documented it as a daily job for four days. Enabled via the REST API (`PATCH /api/repos/2/cron/2`) — the CLI's
  `repo cron update` 404s on a positional repo argument. `next_exec` now reads 2026-08-23 01:00 EDT.
  **Lesson for any new timer: `--enabled` is not a default, and a disabled cron is silent.** Verify a new
  schedule by checking `next_exec` is in the FUTURE, not merely that the entry exists.
- 2026-08-22 — **Added the `pr-staleness-check` k8s CronJob (B131)** — open-PR staleness watchdog on
  `edtbl76/weyland-lab`, daily **05:45 NY**, `spec.timeZone` pinned. Drafted at `*/30` and corrected before merge:
  that violated **Design Rule #5** (no mid-day auto-runs) and, because synthetic alerts auto-resolve after 5m and
  re-fire as NEW alerts, would have sent ~48 Telegram messages a day per stale PR. The budgets are measured in days,
  so daily is proportionate. Note for a future sweep: `dagster-freshness-check` (`*/30`, `k8s/dagster/freshness.yaml`)
  is **absent from this table** and is itself a mid-day auto-run — an undocumented Rule #5 exception, not a precedent.
- 2026-08-20 — **Added the `restic-backup` rogueone systemd timer (B130)** — encrypted incremental restic → MinIO
  `rogueone-backup`, daily 02:30 NY (+≤30m jitter), user unit + `loginctl enable-linger`. Off-hours ✓; on rogueone
  (not mother) so it doesn't stack on the single node. Reports Port `backup` + a Kuma push dead-man's-switch.
- 2026-08-18 — **Added the `nightly-images` Woodpecker cron (B57a)** — weyland image CI build pipeline on
  `edtbl76/weyland-lab`, `0 5 * * *` **UTC** = 01:00 EDT / 00:00 EST. Placed at 01:00 NY to clear the 02:00
  scaledown + the 02:17 `weyland_ingestion` HEAVY; only overlaps the light 01:00 DataHub Grafana scan. First entry
  of a new timer class — **Woodpecker crons run in UTC**, not NY-pinned (added to the TZ table + Design Rule #1).
- 2026-08-07 — **No mid-day auto-runs (incident-driven).** Moved the every-N-hour Dagster schedules to a single
  pre-dawn tick each — `timeseries` 00:20, `datahub_catalog_emit` 00:35, `catalog` 00:50 (were every 4h/6h,
  firing at noon). Trigger: the noon cluster stacked on a manual datasets-hydrate + a raised Cockroach disk-stall
  threshold (which removed the crash that used to fail-fast the hydrate) saturated mother — control plane
  unreachable, k3s restart hung, recovery via OS-level `pkill`. New Design Rule #5 + a DoD rule: mid-day = manual-only.
- 2026-07-04 — Added Kafka (Redpanda B1.5) DataHub ingestion → 02:15 daily (light metadata scan of the
  `datasets.*` event topics + their Avro schemas; closes the last B65 catalog target).
- 2026-07-02 — Added ClickHouse (Tier-2 #10) DataHub ingestion → Sun 04:30 (weekly; profiling on — columnar
  counts are cheap, unlike Cassandra).
- 2026-07-02 — Added Cassandra (Tier-2 #9) DataHub ingestion → Sun 04:15 (weekly, static data; profiling
  table-level but lastfm excluded — a 17M-row Cassandra COUNT would hammer the single node).
- 2026-07-02 — Pinned all Dagster schedules to `America/New_York` (were UTC). Added the `02:00`
  data-mesh scale-down CronJob + per-store Port wake actions. Recommended DataHub ingestion stagger;
  CockroachDB → `30 3 * * *` (weekly `30 3 * * 0`).

# Weyland — Master Schedule

Single source of truth for **everything that runs on a timer** in the lab: Dagster schedules,
DataHub managed-ingestion sources, k8s CronJobs, and **node systemd timers** (mother + rogueone). Keep this updated whenever a
schedule is added, moved, or disabled (same discipline as [hosts.md](hosts.md) / [api.md](api.md)).

## Timezone — one clock now

As of **2026-07-02**, all timed systems are pinned to **America/New_York**, so what you read in any
UI is what actually runs — no mental TZ conversion:

| System | Timezone | How it's set |
|---|---|---|
| **Dagster** | America/New_York | `execution_timezone="America/New_York"` on every `ScheduleDefinition`. |
| **DataHub** managed ingestion | America/New_York | TZ selector per source in the ingestion UI. |
| **k8s CronJob** (scale-down) | UTC by convention → set `.spec.timeZone` | k8s CronJobs default to the kube-controller-manager's TZ; set `spec.timeZone: America/New_York` explicitly. |

> **History:** before the pin, Dagster schedules ran in **UTC** while DataHub ran in EDT — a `12 am`
> DataHub source was really `04:00 UTC`, colliding with Dagster's `ai_session`. The pin removed that trap.

## Master timetable (America/New_York)

Heavy = embeds/writes or large scans (guard the node's RAM). Light = metadata/read-only.

| Time (NY) | System | Job / source | Cadence | Weight |
|---|---|---|---|---|
| **02:00** | k8s CronJob | `data-mesh-scaledown` → cockroachdb/mongodb/mysql/gizmosql to 0 | daily | — (frees RAM) |
| **02:17** | Dagster | `weyland_ingestion_job` (RAG fan-out, serialized) | daily | **HEAVY** |
| 00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00 | Dagster | `ai_session` | every 4h — ⚠️ **STOPPED, never enabled** (0 ticks; the job has 1 FAILURE 2026-06-26 and NO successful run ever). The B62 AI-Dev Usage product has therefore ingested nothing since June, while the rogueone **producer** kept mirroring to MinIO. Enable only after a manual `weyland_ai_session_job` run passes — see B94. | light |
| 00:25 / 04:25 / 08:25 / … | Dagster | `timeseries` (→ TimescaleDB hypertables) | every 4h | med |
| 00:40 / 06:40 / 12:40 / 18:40 | Dagster | `datahub_catalog_emit` (custom emitters) | every 6h | light |
| 00:50 / 06:50 / 12:50 / 18:50 | Dagster | `catalog` (model lookup) | every 6h | light |
| 03:00 | Dagster | `datasets_music_land` | daily — **RUNNING** (enabled in the UI; code `default_status` is STOPPED, which only applies at first registration) | light in practice — assets **self-skip if fresh** (30-day window), so the ~342 MB FMA download is rare, not daily |
| 04:00 | Dagster | `datasets_health_land` | daily — **RUNNING** (as above) | light in practice — self-skips if fresh (7-day window) |
| **06:00** | Dagster | `weyland_dbt_job` (dbt build → 7 marts + tests; then publishes `manifest.json`+`catalog.json` to `s3://warehouse/_dbt_artifacts/`) | **weekly (Sun)** | **HEAVY** — Trino aggregations (4G heap; `approx_distinct`/`threads:2` guard the OOM) |
| 01:00 | DataHub | Grafana | daily | light |
| 01:15 | DataHub | Iceberg (Nessie) | daily | light |
| 01:30 | DataHub | MLflow | daily | light |
| 01:45 | DataHub | Superset | daily | light |
| 02:15 | DataHub | Kafka (Redpanda `datasets.*` topics + Avro schemas) | daily | light — metadata scan, no profiling |
| `0 */6 * * *` | k8s CronJob | `lancedb-sync` (mc mirror lakeFS Lance tables → viewer PVC) | every 6h | light — in practice the **PRIMARY** path, not a backstop. `lancedb_sync_sensor` watches `datasets_{music,health}_lancedb_load`, which live in the `datasets_*_stores` groups — **hydration is deliberately ON-DEMAND** (the hydrate jobs have no schedule), so the sensor idles for weeks by design and skips cleanly. A long-idle `lancedb_sync_sensor` is EXPECTED, not a fault. |
| 03:00 | DataHub | Neo4j | daily | light |
| 03:15 | DataHub | Postgres (weyland core) | daily | med |
| **03:30** | DataHub | **CockroachDB** | weekly (Sun) | med |
| 03:45 | DataHub | MongoDB | weekly (Sun) | med |
| 04:15 | DataHub | Cassandra (datasets_music + datasets_health) | weekly (Sun) | med — profiling excl. lastfm |
| 04:30 | DataHub | ClickHouse (datasets_music + datasets_health) | weekly (Sun) | med — profiling cheap (columnar) |
| 04:45 | DataHub | Postgres — MusicBrainz | weekly (Sun) | **heavy scan** |
| 05:00 | DataHub | dbt (marts + tests-as-assertions + column lineage; reads `s3://warehouse/_dbt_artifacts/`, siblings onto `iceberg.dbt.*`) | daily | light — recommend 05:00 to clear the 01:00–04:45 DataHub train. Daily connector over **weekly** (Sun 06:00) artifacts = harmless idempotent re-ingest most days; fresh artifacts land ≤1 day after a build. |
| **08:00 (Sun)** | k8s CronJob | `sonar-scan` (SonarQube full analysis → the SonarQube server; clone + Flink-Java compile + sonar-scanner) | weekly (Sun) | med — Java build + scan (12:00 UTC) |
| **09:00 (Sun)** | k8s CronJob | `code-scan-suite` (gitleaks/checkov/kubescape/hadolint/bandit/osv-scanner/shellcheck/semgrep/trivy → Port + code-maat hotspots; one `scan-suite` image) | weekly (Sun) | **HEAVY** — semgrep auto + trivy fs (13:00 UTC) |
| **11:00 (Sun)** | node systemd (mother) | `weyland-image-prune` (`k3s crictl rmi --prune`) — frees ephemeral storage so the node never re-hits the eviction line (B69, `nodes/mother/host/systemd/`) | weekly (Sun) | — (host timer @ **15:00 UTC**; quiet slot clear of the DataHub train) · **INSTALLED 2026-07-20** (authored 07-18, enabled 07-20) |
| **05:30** | k8s CronJob | `docs-site-rebuild` — `kubectl rollout restart deploy/docs-site` (B69). docs-site rebuilds from a fresh `git clone` on every pod start, so without this the site silently serves a snapshot frozen at the last restart. No push-trigger available ([[lan-no-github-webhooks]]). | daily | light — restart only; the mkdocs build happens in the new pod's initContainer |
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
| `roadmap-sync.{service,timer}` | CT 104 (Hermes) | daily 06:30 | Hermes is shut off — install when **B66** brings an agent back |
| `hermes-heartbeat.{service,timer}` | CT 104 (Hermes) | every 60s → Kuma Push | same; also needs the Kuma Push monitor created (120s interval) |

> **⚠ rogueone GPU contention (affects the Sat eval runs).** rogueone has ONE GPU (RTX 5000 Ada Laptop, **16 GB**)
> and no usable iGPU, so it drives the desktop AND Ollama. A 30b model can starve the compositor and **hard-freeze
> the desktop** while Ollama keeps serving normally (no OOM/Xid/panic — it only looks broken from the keyboard).
> Guardrails: `nodes/rogueone/systemd/ollama-gpu-guardrails.conf` (max 1 loaded model, 30s keep-alive, 1.5 GiB
> reserved) — **validated 2026-07-20 under contention**: a full matrix + 3-judge scoring pass completed with the
> desktop in active use, no freeze. BIOS → Hybrid Graphics is the structural fix but is **deferred, not needed**.

**Ordering note (risk currently DORMANT):** a nightly `02:00` scale-down *would* take
cockroach/mongo/mysql/gizmosql to 0, and the DataHub ingestions that read them (Cockroach 03:30, Mongo
03:45, both **weekly Sun**) would then hit a scaled-to-zero store. **But the auto sleep/scale-down is
PARKED** — Argo `selfHeal` reverts `replicas:0` (see [runbooks/port-agent-easy-button.md](runbooks/port-agent-easy-button.md)
and [[store-scaler-easy-button]]), pending KEDA-in-Argo. Stores stay up overnight, so 03:30/03:45 are
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

## Design rules

1. **One clock** — everything in America/New_York. New timers inherit it explicitly.
2. **Spread the heavy stores** — Postgres-core, Cockroach, Mongo, MusicBrainz never share a 15-min slot.
3. **Static data → weekly, not daily** — Cockroach (brfss/nhis), the Mongo *datasets*, and MusicBrainz
   were loaded once; daily re-profiling just re-scans them. Weekly is enough.
4. **One node, one RAM pool** — Dagster runs execute *in* the user-code pod; DataHub ingestion in its
   executor; both draw on mother's ~32 GB. Staggering + scale-down are memory guards, not tidiness.

## Change log

- 2026-07-04 — Added Kafka (Redpanda B1.5) DataHub ingestion → 02:15 daily (light metadata scan of the
  `datasets.*` event topics + their Avro schemas; closes the last B65 catalog target).
- 2026-07-02 — Added ClickHouse (Tier-2 #10) DataHub ingestion → Sun 04:30 (weekly; profiling on — columnar
  counts are cheap, unlike Cassandra).
- 2026-07-02 — Added Cassandra (Tier-2 #9) DataHub ingestion → Sun 04:15 (weekly, static data; profiling
  table-level but lastfm excluded — a 17M-row Cassandra COUNT would hammer the single node).
- 2026-07-02 — Pinned all Dagster schedules to `America/New_York` (were UTC). Added the `02:00`
  data-mesh scale-down CronJob + per-store Port wake actions. Recommended DataHub ingestion stagger;
  CockroachDB → `30 3 * * *` (weekly `30 3 * * 0`).

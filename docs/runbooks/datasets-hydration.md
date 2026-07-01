# Datasets hydration — silver → Tier-2 stores (data-store-mageddon)

The third `datasets_lib` factory. After the transform builds silver/gold (see
[datasets-lake.md](datasets-lake.md)), **`build_store_load_assets(cfg)`** reads the silver **Parquet**
from lakeFS and loads it into the Tier-2 stores the storage grid targets — one loader asset per store,
driven by **explicit per-store allowlists** on `DomainConfig`. A store gets a loader asset only when its
allowlist is non-empty, so the same factory call produces exactly the loaders a domain needs and nothing more.

```text
lakeFS  parquet/<dataset>/<file>.parquet   (silver)
        │
        │  build_store_load_assets(cfg)        ← reads cfg.<store>_allow
        ▼
   datasets_<domain>_<store>_load  (one asset per targeted store)
        │   batched: pyarrow iter_batches → pandas → store write
        ▼
   MySQL · (ClickHouse · Cassandra · CockroachDB · Mongo · Neo4j · OpenSearch · Qdrant · Weaviate · Feast …)
```

Three factories now ride one `DomainConfig`:
`build_transform_assets` → `build_asset_checks` → `build_store_load_assets`.

## Per-store discipline (the two standing calls)

Before building any store's loader, answer two questions (and gate on them):
1. **Where's the real data source?** — almost always the silver **Parquet** (`parquet/<dataset>/`). Loaders
   read Parquet, not raw, so they inherit the cleaning (name-normalize, null-coerce) and the quality checks.
2. **Always-on or KEDA'd?** — `kubectl -n data-mesh get scaledobject,deploy | grep -i <store>`. A
   `ScaledObject` means the loader must trigger/await scale-up; a plain `Deployment` means load directly.

The loader asset `deps` on `datasets_<domain>_parquet`, so it runs after silver exists and the parquet
**`no_failures`** blocking check gates it — bad silver never hydrates.

## Completeness gate — run after EVERY store (not "it ran once")

A store is not done when the loader goes green once. Before marking a store complete, verify all seven —
and record the result (the gate exists to surface the gaps a single successful run hides):

| # | Check | How |
|---|---|---|
| 1 | **Loaded** — every target dataset present, row counts sane | `information_schema` counts vs the `<store>_allow` set |
| 2 | **Runnable** — a hydrate **job** (schedulable), not just a materializable asset | `define_asset_job` selecting the store loader |
| 3 | **Gated** — the parquet `no_failures` check gates the load (bad silver can't hydrate) | loader `deps` on `datasets_<domain>_parquet` |
| 4 | **Cataloged** — DataHub lineage silver → store | emit from the loader (or a native store source) |
| 5 | **Monitored** — store health + load-failure alert | Uptime Kuma monitor + Loki/Alertmanager rule |
| 6 | **Documented** — runbook + arch/hosts/api | this file + arch.md §7 + hosts.md/api.md |
| 7 | **Pushed** — code + manifests (GitOps) | git push; Argo for k8s manifests |

### MySQL — gate result (2026-07-01, punch-list closed → pending deploy+verify)
- ✅ **1 Loaded** — 32 tables, all 6 DBs.
- ✅ **2 Runnable** — `weyland_datasets_health_hydrate_job` (group `datasets_health_stores`; loaders live in
  their own group so the transform job never runs them).
- ✅ **3 Gated** — the loader `deps` on `datasets_health_parquet`; its blocking `no_failures` check gates hydration.
- ✅ **4 Cataloged** — `emit_mysql()` (platform `mysql`, schema from information_schema, lineage ← the
  `datasets.<db>` parquet silver) wired into the hourly `datahub_catalog_emit_job`.
- ~ **5 Monitored** — Loki **`WeylandDatasetHydrationFailure`** rule → Alertmanager → Telegram (catches even
  a single swallowed per-table failure). Store-*up* monitoring via Uptime Kuma is blocked by Kuma's LAN-DNS
  (can't resolve `*.svc.cluster.local`, see [[kuma-lan-dns-monitors]]); MySQL is always-on + meshed, so a
  proper up-monitor = a Prometheus `mysqld-exporter` (deferred — noted, not silently skipped).
- ✅ **6 Documented** — this runbook + arch.md §7 + hosts.md/api.md + `flow-datasets-lakehouse.md`.
- ▢ **7 Pushed** — pending (code + `k8s/loki/loki-rules-configmap.yaml`).

**MySQL closes the gate once deployed + verified** (hydrate job runs green as a job; DataHub shows the
mysql datasets + lineage; the alert rule loads). The one accepted gap is store-up monitoring (Kuma LAN-DNS
constraint) — a `mysqld-exporter` is the follow-up. Same 7-point gate applies to every store after.

## MySQL (store #1 — loaded; completeness punch-list open)

- **Deploy:** `mysql.data-mesh.svc:3306`, **always-on** (`deployment.apps/mysql`, no ScaledObject), user
  `weyland` / shared dev password. 6 databases pre-created, empty, matching the grid.
- **Targets (grid `MySQL=Y`):** `nhanes`, `big_five`, `who_gho`, `cdc_physical_activity`, `brfss`, `nhis`
  (health). USDA + Open Food Facts are `MySQL=N`; all music is `N`.
- **Mapping:** **dataset → database** (pre-created), **each parquet file → a table** (e.g. the `nhanes` DB
  gets `t_2017_2020_demo_j`, `t_2015_2016_bmx_i`, … one per XPT cycle file; `brfss` gets its per-file tables).
  Table names via `_sql_ident` (non-`[A-Za-z0-9_]` → `_`, digit-leading guard).
- **Write:** `pandas.to_sql` over a `mysql+pymysql://` SQLAlchemy engine per database; **batched**
  (pyarrow `iter_batches(50k)` → pandas → `to_sql(..., if_exists="replace"` on first batch then `"append")`)
  so big tables (brfss ~3M rows) stay memory-bounded. `to_sql` auto-creates the table from the Arrow→pandas schema.
- **Driver:** `SQLAlchemy` + `PyMySQL` (added to the user-code image's requirements).
- **Connection:** `MYSQL_HOST/PORT/USER/PASSWORD` env on the user-code deployment (`k8s/dagster/user-code.yaml`).
- **Asset:** `datasets_health_mysql_load` — materialize it (or run the future hydrate job) after the health
  transform is green.

## TimescaleDB (store #2 — WHO GHO hypertables, 2026-07-01)

- **Target (grid `TimescaleDB=Y`):** `who_gho` only. Last.fm is `Y` in the grid but **skipped** — its silver is
  lifetime user↔artist playcounts with no per-listen timestamps, so it isn't a time-series (only `signup_date`
  is temporal; forcing it in would be square-peg cruft). Recorded in the `timescale_allow` comment.
- **Loader:** `datasets_health_timescaledb_load` (the `timescale_allow={"who_gho": "TimeDim"}` arm of
  `build_store_load_assets`). Each WHO GHO indicator parquet → a **hypertable** in db `timeseries`, named
  `who_gho_<indicator>` (dataset-prefixed — TimescaleDB is one flat db). Time axis: a derived `ts` timestamptz
  = `TimeDim` (the year) → Jan 1; rows with no usable year are dropped (a hypertable's time column must be non-null).
  `to_sql` then `create_hypertable(..., migrate_data => TRUE, if_not_exists => TRUE)`.
- **Connection:** the existing `TIMESCALEDB_*` defaults (`timescaledb.data-mesh.svc:5432`, db `timeseries`,
  `weyland`/dev pw) — no new env. Runs in `weyland_datasets_health_hydrate_job` (same `datasets_health_stores` group).
- **Gate:** Loaded ✅ · Runnable ✅ · Gated ✅ (parquet dep) · Cataloged ✅ (`emit_timescaledb` scans all
  hypertables) · Monitored ✅ (rides the hydrate-failure Loki rule) · Documented ✅ · Pushed ▢.

## Store roadmap (the grid's Tier-2 targets)

| Store | Deployed? | Loader | Grid targets (datasets) |
|---|---|---|---|
| **MySQL** | ✅ always-on | ✅ **done** | health: nhanes, big_five, who_gho, cdc_physical_activity, brfss, nhis |
| TimescaleDB | ✅ | ✅ **done** | who_gho (country/year → 8 hypertables). Last.fm **skipped** — its silver is lifetime playcounts, no per-listen timestamps (not a real time-series) |
| Neo4j | ✅ (RAG) | ▢ | graphs: fma_genres, fma_tracks, uci, lastfm, musicbrainz, audioset, big_five |
| OpenSearch | ✅ (RAG) | ▢ | search: fma_tracks, uci, musicbrainz, lp_musiccaps_*, audioset, usda, open_food_facts |
| Qdrant / Weaviate | ✅ (RAG) | ▢ | vector similarity (the Lance-allowlisted sets) |
| ClickHouse | ▢ deploy first | ▢ | OLAP: fma_features, uci, audioset, who_gho, brfss, nhis, usda, open_food_facts |
| Cassandra | ▢ deploy first | ▢ | uci, lastfm, big_five, who_gho |
| CockroachDB | ▢ deploy first | ▢ | brfss, nhis (geo-partitioned) |
| MongoDB | ▢ deploy first | ▢ | who_gho (nested JSON), open_food_facts (doc per product) |
| Feast | ▢ deploy first | ▢ | feature store (audio/health features) |

Each new store = a `<store>_allow` field on `DomainConfig` + a writer arm in `loaders.py` + (if not
deployed) standing up the store first. Full per-dataset targets in [data-pipeline-flows.md](../data-pipeline-flows.md).

## Deploy

The loader is in the user-code image **and** adds Python deps (`SQLAlchemy`, `PyMySQL`) — so rebuild the
image (the `:local` procedure in [validation/test-commands.md](../validation/test-commands.md)) and **push
`k8s/dagster/user-code.yaml`** (the new `MYSQL_*` env) so Argo rolls the deployment.

```bash
# verify load (in-pod) — table counts per MySQL database after running datasets_health_mysql_load
kubectl -n data-mesh exec deploy/mysql -- sh -c 'mysql -uweyland -pweyland_dev_password -e "SELECT table_schema db, COUNT(*) tables FROM information_schema.tables WHERE table_schema IN (\"nhanes\",\"big_five\",\"who_gho\",\"cdc_physical_activity\",\"brfss\",\"nhis\") GROUP BY table_schema;"' 2>/dev/null
```

## Status (2026-07-01)

- ✅ **MySQL — LOADED + verified** (completeness punch-list open: job, DataHub lineage, monitoring — see the
  completeness gate above). `datasets_health_mysql_load` hydrated all 6 DBs: **32 tables** (nhanes 13,
  who_gho 8, brfss 6, nhis 3, cdc 1, big_five 1). Proved the full vertical: land → silver → quality checks →
  hydration. Two fixes surfaced and were made at the right layers: **big_five's TSV** (fixed at *land* —
  `data.csv` is tab-separated → convert to comma-CSV; flowed through every format + store for free) and the
  **`to_sql` insert method** (`method="multi"` compiles chunksize×columns bind params → hung on big_five's
  57 columns → switched to the default `executemany`). `RefreshConfig.force` was wired into big_five for a
  wipe-free re-land.
- ▢ Remaining stores per the roadmap table. Deploy-gated ones (ClickHouse/Cassandra/CockroachDB/Mongo/Feast)
  need standing up before their loader.
- ▢ Quality gate wiring (B77 native checks already gate via the parquet dep; GE → DataHub Assertions = later).

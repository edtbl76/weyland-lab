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

### MySQL — gate result (2026-07-01)
- ✅ **1 Loaded** (32 tables, all 6 DBs) · ✅ **6 Documented** · ~ **3 Gated** (loader deps on parquet, but the
  load is a separate materialization — tighter gating comes with the job in #2)
- ✗ **2 Runnable** — no hydrate *job* yet, only the materializable `datasets_health_mysql_load` asset → TODO
- ✗ **4 Cataloged** — the loader doesn't emit to DataHub; no silver→MySQL lineage → TODO
- ✗ **5 Monitored** — no load-failure alert; confirm MySQL is in Uptime Kuma → TODO
- ▢ **7 Pushed** — pending

**So MySQL is _loaded_, not _complete_.** Punch-list before it fully closes: a **hydrate job** (+ schedule),
**DataHub lineage** from the loader, and **monitoring/alerting**. Same gate applies to every store after.

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

## Store roadmap (the grid's Tier-2 targets)

| Store | Deployed? | Loader | Grid targets (datasets) |
|---|---|---|---|
| **MySQL** | ✅ always-on | ✅ **done** | health: nhanes, big_five, who_gho, cdc_physical_activity, brfss, nhis |
| TimescaleDB | ✅ | ▢ | lastfm (listening trends), who_gho (country/year) |
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

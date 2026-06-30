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

## MySQL (store #1 — DONE)

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

## Status (2026-06-30)

- ✅ **MySQL loader built** — `build_store_load_assets` + the 6 health DBs. Pending first run + verify.
- ▢ Remaining stores per the roadmap table. Deploy-gated ones (ClickHouse/Cassandra/CockroachDB/Mongo/Feast)
  need standing up before their loader.
- ▢ Quality gate wiring (B77 native checks already gate via the parquet dep; GE → DataHub Assertions = later).

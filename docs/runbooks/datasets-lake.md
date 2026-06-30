# Datasets lake — music + health domains (bronze → silver → gold) · B72 / B75

A **bronze → silver → gold** lakehouse over public **music** and **health** datasets, built on the data
mesh (lakeFS + Nessie + MinIO + DataHub). Per-dataset Dagster **land** assets pull source files → lakeFS
`raw/` (bronze); a shared **transform broker** fans each raw table out to five silver formats
(Parquet/Arrow/Avro/Lance) + hydrates **Iceberg** gold; DataHub catalogs it all. Tracked: backlog B72/B75.

## Shared platform — `datasets_lib`

The two domains are ~identical mechanism, so it lives **once** in `weyland_pipeline/assets/datasets_lib/`
and each domain is a thin `DomainConfig` + `build_transform_assets(cfg)`. Adding a domain = a config, not
a new module. (Extracted 2026-06-30 after the two transforms had drifted into ~90% copy-paste.)

| Module | Owns |
|---|---|
| `io.py` | lakeFS/MinIO client, `put`/`put_raw`/`fput_raw` (streamed), key prefixing — parameterized by repo |
| `freshness.py` | last-materialization + remote-HEAD freshness checks; **`RefreshConfig.force`** override |
| `readers.py` | extension-dispatch reader (`csv`/`csv.gz`/`xpt`/`json`), `sanitize_columns`, `coerce_null_cols`, `iter_raw_tables` |
| `writers.py` | the 5 format writers + `ice_ident` (per-file naming) + `SkipTable` + `ICEBERG_MAX_ROWS` |
| `config.py` | `DomainConfig` dataclass (repo, namespace, group, per-format allowlists, land deps) |
| `broker.py` | `build_transform_assets(cfg)` → the 5 format assets + `_commit`, names `datasets_<domain>_<fmt>` |

`music_common.py` / `health_common.py` are now **thin repo-bound facades** over `datasets_lib` (so the
~20 land assets keep their imports unchanged). The store-loader phase (data-store-mageddon) should add a
`build_store_load_assets(cfg)` factory the same way.

## Architecture

```text
per-dataset land asset (HF / CDC / Socrata / zip / gz)
        │  freshness-gated (RefreshConfig.force bypasses) · big HF datasets streamed to a temp file
        ▼
lakeFS  music|health / raw/<table>/<file>.{csv,xpt,json,csv.gz}      (BRONZE)
        │
        │  weyland_datasets_<domain>_transform_job  (manual / scheduled; serialized, max_concurrent=1)
        ▼
build_transform_assets(cfg) — one asset PER format, each its own process (the asset graph is the broker)
   ┌──────────┬──────────┬──────────┬──────────┬─────────────────────┐
 parquet/    arrow/      avro/      lance/        Iceberg (Nessie)        + _commit (versions lakeFS)
 (SILVER · columnar / IPC / row-streamed / vector)   (GOLD · datasets_<domain>.<table>_<file>)
        │
        ▼
DataHub — custom emit (emit_file_dataset) for raw + 4 silver formats · iceberg source for gold
```

## Domains & configs

| | repo | namespace | group | land assets |
|---|---|---|---|---|
| **music** | `music` | `datasets_music` | `datasets_music` | spotify_tracks, fma_tracks/genres/echonest/features, uci_year_prediction, lastfm, musicbrainz, gtzan, lp_musiccaps_mc/mtt, audioset (12) |
| **health** | `health` | `datasets_health` | `datasets_health` | nhanes, big_five, who_gho, cdc_physical_activity, brfss, nhis, usda_fooddata, open_food_facts (8) |

## Formats & why each earns its spot

| Format | Layer | Lib | Purpose |
|---|---|---|---|
| **Parquet** | silver | pyarrow | batch analytics (Trino / DuckDB) — the default columnar |
| **Arrow/Feather** | silver | pyarrow | in-memory / IPC zero-copy (polars / JupyterHub). *Transport, not true storage — kept for learning* |
| **Avro** | silver | fastavro | row-oriented, schema-evolution, **streaming** (Kafka). **Written streamed** (50k-row batches) — `to_pylist()` on the whole table OOM'd the node |
| **Lance** | silver | pylance | **ML / vector** — fast random access, versioning, LanceDB. Native Rust S3 writer (isolated per-asset) |
| **Iceberg** | gold | pyiceberg | ACID tables, time-travel, schema evolution over Parquet, in Nessie |

## Key behaviors (all in `datasets_lib`, both domains)

- **Per-format allowlists** (`config.py`, explicit — the storage grid is a *guideline*, not config). A table
  absent from a format's set is skipped **before the read** (so deferred 9GB sources and Lance-excluded
  row-heavy sets never pay the download cost). Parquet/Arrow/Avro/Iceberg ≈ all; **Lance is selective**.
- **Per-file table/dataset naming** (`ice_ident`, and Lance path `lance/<table>/<file>`). Naming Iceberg
  by *folder* made multi-file folders (usda's 30 CSVs, musicbrainz splits, audioset train/test) overwrite
  one table — only the last survived. Now each file → its own table.
- **Iceberg size guard** — `ICEBERG_MAX_ROWS = 15M`. A bigger table raises `SkipTable` → recorded
  `deferred`, not a hang. Writing huge parquet to the warehouse stalls with no timeout (usda
  `food_nutrient` ~24M rows hung the step 30m, CPU=0). Deferred tables still land in the file formats.
- **Null-type coercion** — `coerce_null_cols` casts all-null (`pa.null()`) columns to `string` before
  Iceberg (v2 rejects null type; hits WHO GHO unused `Dim*Type`, NHIS flags, some usda cols). Iceberg-only.
- **Column-name normalization** — `sanitize_columns` rewrites every name to a valid identifier (empty →
  `column_<i>`, non-`[A-Za-z0-9_]` → `_`, leading-digit guard, de-dup). Empty/special names break the
  strict writers: avro rejects empty, Lance rejects `.` (an FMA header leaked a URL into a column name),
  Iceberg's avro manifests reject empty, DataHub 422s an empty field path.
- **Serialized execution** — the transform jobs run `multiprocess` `max_concurrent: 1` (in `schedules`).
  5 formats racing each re-read all of `raw/` → 5× peak memory → node OOM. One-at-a-time = 1× peak.
- **Freshness + force** — land assets skip when fresh; materialize with launchpad config `{"force": true}`
  (`RefreshConfig`) to re-download without the destructive "wipe materializations" hack.
- **Streaming large HF sources** — musicbrainz streams `load_dataset(streaming=True)` row-by-row to a temp
  file then `fput`s it (the non-streaming load + in-memory CSV buffer OOM'd).

## Deploy (user-code image)

Code is **baked into the image** — rsync + rebuild, not a hot reload. The deployment runs the **`:local`**
tag with `imagePullPolicy: Never`, and **`ctr import` won't overwrite an existing tag**, so remove it first.

```bash
# rogueone — sync source
rsync -av <repo>/services/weyland-dagster/weyland_pipeline/ emangini@mother:~/lab/.../weyland_pipeline/
# mother — rebuild :local, force-replace in containerd (k8s.io ns), restart
docker build -t weyland-dagster-user-code:local ~/lab/.../weyland-dagster/
sudo k3s ctr -n k8s.io images rm docker.io/library/weyland-dagster-user-code:local
docker save weyland-dagster-user-code:local | sudo k3s ctr -n k8s.io images import -
docker image prune -f --filter "until=24h"      # mandatory — full accumulation caused 153GB + DiskPressure
kubectl -n weyland rollout restart deployment/dagster-user-code
# GATE — the whole import graph must load:
kubectl -n weyland exec deploy/dagster-user-code -- python -c "import weyland_pipeline.definitions as d; print('defs OK')"
```

The user-code pod has a **12Gi memory limit** (`k8s/dagster/user-code.yaml`): `DefaultRunLauncher` runs
jobs *inside* the pod, so an unbounded heavy run triggered node-wide OOM that killed other lab pods. The
limit contains it to a pod-scoped restart. The daemon is separate — `dagster.yaml` (`configmap.yaml`) sets
`QueuedRunCoordinator` `max_concurrent_runs: 2` + `run_monitoring max_runtime_seconds: 3600` (kills a hung
run after 1h; note the key is `max_runtime_seconds`, not `run_timeout_seconds`). Daemon config changes need
`rollout restart deployment/dagster-daemon`.

## Gotchas (hard-won this build)

- **`:latest` vs `:local`** — the deployment mounts `:local`; a `:latest` build imports fine but nothing
  runs it. Always build/import `:local`.
- **Nessie nested namespaces invisible to Trino** (`catalog.type=nessie`) → flat `datasets_<domain>`.
- **Schema-change on an existing Iceberg table** — if a prior run baked a bad field (empty name) into the
  table, `union_by_name` can't reconcile it; **drop + recreate** (`_catalog().drop_table(...)`).
- **Stale raw twins / cruft** — duplicate `<timestamp>.<hash>.csv` files and old clobber-era folder tables
  accumulate from earlier iterations; one-time cleanup (delete from lakeFS raw + `drop_table`), then
  per-file naming + normalize prevent recurrence.
- **NHANES URLs moved** — CDC reorganized `wwwn.cdc.gov`; old `/Nchs/Nhanes/<cycle>/<F>.XPT` 302 to HTML
  (silently landing HTML). Current: `/Nchs/Data/Nhanes/Public/<firstYear>/DataFiles/<F>.xpt`.

## Status (2026-06-30)

- ✅ **Music** — 12 datasets, all 5 formats + commit green (musicbrainz partial — only `artist` landed; the
  big splits OOM'd, re-land pending — the dataset is only 1.37 GB, an environmental OOM not a size problem).
- ✅ **Health** — 8 datasets green; `open_food_facts` (~9GB `.csv.gz`) and usda `food_nutrient` (~24M rows)
  **deferred** by design (still in the other formats).
- ▢ **Store loaders** — the grid's Tier-2 targets (MySQL/Mongo/ClickHouse/Cassandra/CockroachDB/Neo4j/
  OpenSearch/Qdrant/Weaviate/Feast) — next phase ("data-store-mageddon"), to be built as a
  `build_store_load_assets(cfg)` factory.
- ▢ **Deferred big-data** — chunked `open_food_facts` reader + large-table Iceberg writer for `food_nutrient`.
- ▢ **Data quality** — asset-checks / Great Expectations → DataHub Assertions (B77, after the store loaders).

> Diagram is ASCII; D2/Mermaid migration tracked in B64.

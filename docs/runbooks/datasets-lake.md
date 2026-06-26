# Datasets lake — music data (bronze → silver → gold)  ·  B72

A real **bronze → silver → gold** pipeline over public music datasets (Spotify audio features,
FMA metadata), built on the existing data mesh. **dlt** extracts → **MinIO** lands raw → a
**pyarrow** transform fans out to five formats + hydrates **Iceberg** → **DataHub** catalogs it all.
Ties to Stud.IO + the Spotify Hermes tool (B18). Tracked: backlog B72 / Linear EMA-62.

## Architecture

```text
HF / FMA ──▶ dlt (EL, in Dagster) ──▶ MinIO  datasets/raw/{table}/     (BRONZE · source CSV)
                                            │
                                            │  Dagster @sensor (polls raw/ for new objects)
                                            ▼
                                  Dagster transform asset (pyarrow)
              ┌──────────┬──────────┬──────────┬──────────┬───────────────────┐
          parquet/     arrow/      avro/      lance/        Iceberg (Nessie)
          (SILVER · columnar / IPC / row / vector)            (GOLD · ACID tables)
                                            │
                                            ▼
              DataHub  ──  s3 source (file zones, schema inferred)  +  iceberg source (tables)
```

## Zones (MinIO `datasets` bucket)
- `raw/<table>/` — **bronze**, source CSVs as landed by dlt.
- `parquet/` · `arrow/` · `avro/` · `lance/` `<table>/` — **silver**, the converted formats.
- Iceberg tables (Nessie warehouse) — **gold**, the ACID table layer.

## Formats & why each earns its spot
| Format | Layer | Engine | Purpose |
|---|---|---|---|
| **Parquet** | silver | pyarrow | batch analytics (Trino / DuckDB / Spark) — the default columnar |
| **Lance** | silver | pylance | **ML / vector** — fast random access, versioning, LanceDB |
| **Avro** | silver | fastavro | row-oriented, schema-evolution, **streaming** (the format you'd push through Kafka) |
| **Arrow / Feather** | silver | pyarrow | in-memory / IPC — fast zero-copy loads. *Honest note: transport format, not a true storage layer — kept for learning* |
| **Iceberg** | gold | pyiceberg | ACID table format, time-travel, schema evolution (over Parquet, in Nessie) |

## Components
- **Extract (EL):** **dlt** run inside Dagster — pulls Spotify (HuggingFace, no auth) + FMA (CC-licensed zip). Public HTTPS, no creds, no legwork.
- **Storage:** **MinIO** (`datasets` bucket) — same object store as the Iceberg warehouse + lakeFS.
- **Transform (brokered):** **one Dagster asset per format** (`datasets_parquet` / `_arrow` / `_avro` / `_lance` / `_iceberg`), all `deps=[datasets_land]`. The asset graph is the broker — Dagster's multiprocess executor runs each in its own child process, so a failure (even a *native* Lance crash) is isolated to that format; the rest still land. pyarrow engine; raw read with `newlines_in_values=True`, bad files skipped not fatal.
- **Trigger:** a plain Dagster **`@sensor`** polling MinIO `raw/` for new objects → launches the transform. NOT a `run_status_sensor` (that's dead on Dagster 1.13 — dagster#21526; see [[dagster-datahub-1.13-blocked]]).
- **Catalog:** DataHub **s3 source** (the file zones, schema inferred) + **iceberg source** (the gold tables).

## Build status (2026-06-26)
- [x] Step 1 — dlt EL → `raw/` · `datasets_land.py`. **Spotify proven** (plain CSV lands); FMA added (multi-header via pandas) — *verify on next run*.
- [x] Step 2 — **brokered** fan-out · `datasets_transform.py`. One asset per format (`datasets_parquet/_arrow/_avro/_lance/_iceberg`), each isolated in its own process so one failure can't sink the rest. Read fixed with `newlines_in_values=True`. *Lance S3 opts are the remaining iteration risk — isolated to `datasets_lance`.*
- [x] Step 3 — S3 `@sensor` · `sensors/__init__.py`. Ships **STOPPED** — enable in Dagster UI after steps 1+2 are green.
- [ ] Step 4 — catalog (s3 source `s3.recipe.yaml` ready; iceberg source covers `datasets.*` gold tables).

**Ops notes:** the `datasets` group is excluded from the 15-min ingestion cron (datasets_land re-downloads external sources). `datasets_land` = on-demand; `datasets_transform` = sensor-triggered (or `deps` chain). FMA zip cached at `/tmp/fma_metadata.zip` in the pod.

> Diagram is ASCII for now; a renderer migration (D2/Mermaid) is tracked in B64.

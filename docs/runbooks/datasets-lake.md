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
- **Catalog:** **all silver formats + the raw CSV are custom-emitted** by the transform assets via `datahub_emit.emit_file_dataset` (typed schema from the Arrow schema + lineage to the producing asset); the **iceberg source** catalogs the gold tables. The DataHub **s3 source is unusable** here — it forces a PySpark run whose Java gateway crashes on the executor image's JDK (`Subject.getSubject` removed in Java 18+), an image-level break no recipe can fix. So one reliable emit path covers raw + Parquet + Avro + Arrow + Lance; iceberg-source for gold.

## Build status (2026-06-26)
- [x] Step 1 — dlt EL → `raw/` · `datasets_land.py`. ✅ Spotify + all 3 FMA tables (multi-header via pandas) land as plain CSV.
- [x] Step 2 — **brokered** fan-out · `datasets_transform.py`. ✅ All five formats green. One asset per format, each isolated in its own process. Read fixed with `newlines_in_values=True`. *(Lance needed AVX-512 → the `cpu: host` Proxmox fix, [[proxmox-vm-cpu-host-avx]].)*
- [x] Step 3 — S3 `@sensor` · `sensors/__init__.py`. ✅ **Enabled + proven** — materializing `datasets_land` auto-fires `weyland_datasets_transform_job` (the five). Hands-off bronze→silver→gold.
- [x] Step 4 — catalog: **custom-emit** for raw CSV + all 4 silver formats (`emit_file_dataset`, fires from each transform asset) + **iceberg source** for `datasets.*` gold. The s3 source was abandoned (PySpark/JDK crash in the executor image — verified dead end, not a recipe issue).

**Ops notes:** the `datasets` group is excluded from the 15-min ingestion cron (datasets_land re-downloads external sources). `datasets_land` = on-demand; `datasets_transform` = sensor-triggered (or `deps` chain). FMA zip cached at `/tmp/fma_metadata.zip` in the pod.

> Diagram is ASCII for now; a renderer migration (D2/Mermaid) is tracked in B64.

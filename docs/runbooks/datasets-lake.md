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
- **Transform:** a **Dagster asset**, **pyarrow** engine — reads raw once into an Arrow Table, writes all five outputs from it.
- **Trigger:** a plain Dagster **`@sensor`** polling MinIO `raw/` for new objects → launches the transform. NOT a `run_status_sensor` (that's dead on Dagster 1.13 — dagster#21526; see [[dagster-datahub-1.13-blocked]]).
- **Catalog:** DataHub **s3 source** (the file zones, schema inferred) + **iceberg source** (the gold tables).

## Build status (2026-06-26)
- [ ] Step 1 — dlt EL → `raw/`
- [ ] Step 2 — pyarrow multi-format transform (parquet/arrow/avro/lance + Iceberg)
- [ ] Step 3 — S3 `@sensor` trigger (new raw → transform)
- [ ] Step 4 — catalog (s3 + iceberg sources)

> Diagram is ASCII for now; a renderer migration (D2/Mermaid) is tracked in B64.

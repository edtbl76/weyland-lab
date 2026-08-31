# Demo — Vector stores: OFF hydration, quality checks, observability (B78)

The demo IS the test: the OFF hydration was RUN end-to-end against the three real vector backends, and
each observability/quality surface was verified live. Captured 2026-08-31.

## 1. Hydration (bounded read → embed → load), per backend

Launched `datasets_health_{qdrant,weaviate,lancedb}_load` (Dagster GraphQL `launchRun`), monitored the
user-code pod's memory throughout — the whole thesis of B78 is that the projected+capped read keeps the
full 200k embed under the 12 Gi pod limit that the old whole-read blew through:

| Backend | Count | Dim | Peak mem |
|---|---|---|---|
| Qdrant  | **200,000** | 384 | 5.9 Gi |
| LanceDB | **200,000** | 384 | 6.6 Gi |
| Weaviate | 195,792 | 384 | 6.1 Gi |

The projected+capped read of the real 4.5M × 211 file peaked at **18.6 MB** (`read_capped`, measured with
tracemalloc in the pod). Payload spot-check (Qdrant): `row_id`=barcode, real OFF data. Weaviate's
195,792-vs-200,000 gap was a silent batch-drop the loader now reports honestly (`_load_dataset_to_weaviate`).

## 2. Quality checks (all three stores)

`vectors_present_and_nondegenerate` is loaded in the live graph (confirmed via GraphQL `assetChecksOrError`).
Its verdict was validated against the live stores — every backend `passed=True` (big_five + open_food_facts,
no empty / degenerate); the degeneracy predicate (`vectors_degenerate`) has unit tests (18 in
`test_parquet_read.py`).

## 3. Observability

- **LanceDB exporter** live (`lancedb-exporter` pod, weyland ns): `/metrics` serves
  `lancedb_table_rows{repo,table}` for all 10 tables; Prometheus ingests it
  (`lancedb_repo_up{health,music}=1`, `lancedb_table_rows{...open_food_facts}=200000`).
- **Grafana dashboard** "Vector Stores" registered (uid `vector-stores`); every panel's PromQL validated
  against live Prometheus — Qdrant `collection_points{id}`, Weaviate `object_count{class_name}`, LanceDB
  from the exporter.
- **Alerts** — `promtool check rules` = SUCCESS (2 rules): `LancedbExporterDown`, `LancedbRepoUnreachable`.

## Teardown

Read-only except: the throwaway Weaviate class `TmpB78FailTest` (created to prove the loader's
`failed_objects` fix, deleted in the same script) and the manual scan/verify Jobs (deleted). All Dagster
runs are normal materializations; no config was hand-edited (repo → Argo).

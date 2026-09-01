# Weyland notebook library (B81)

A semi-exhaustive, **runnable** library demonstrating the whole data / ML / AI stack — each notebook
doubles as a living demo and as documentation of its layer. Open JupyterLab at
[jupyter.weyland.lab](https://jupyter.weyland.lab) and everything here is in `~/notebooks`.

## How it gets here (distribution)

This directory is **git-synced into `~/notebooks` on every spawn** by the singleuser `postStart` hook
(see `../../jupyterhub-values.yaml`) — so the library grows by a `git push`, **no image rebuild**. The
sync **overwrites** the library so it always equals `main`; the image bakes a copy at `/opt/examples` as
an offline fallback. **Do scratch/experimental work elsewhere in your home** (e.g. `~/scratch/`) — the
2 Gi home PVC persists that across spawns, but anything you edit *inside* `~/notebooks` is replaced on
the next spawn.

## The library

### Formats — per-format deep dives
| Notebook | Format | Focus |
|---|---|---|
| `datasets_lake.ipynb` | all four (seed) | polars + DuckDB over the 4 lakeFS silver formats — the original walkthrough |
| `01_format_parquet.ipynb` | **Parquet** | columnar internals: row groups, encodings (RLE_DICTIONARY), compression bake-off, column projection + predicate pushdown |
| `02_format_arrow_ipc.ipynb` | **Arrow / IPC (Feather)** | in-memory columnar standard, zero-copy interop (pyarrow ↔ polars ↔ duckdb ↔ pandas), IPC file vs stream, memory-mapping |
| `03_format_avro.ipynb` | **Avro** | row-based, schema-with-data, **schema evolution** (reader/writer resolution, back/forward compat), codecs |
| `04_format_lance.ipynb` | **Lance** | ML-native columnar: zero-copy **versioning / time-travel**, fast random access (`.take`), a real **IVF_PQ vector index** + ANN |

### Stack layers — *coming next* (B81 waves 2+)
storage/versioning (lakeFS, Nessie/Iceberg) · query/federation (Trino, DuckDB/GizmoSQL, per Tier-2 store)
· vector/graph (Qdrant, **Weaviate** [U16], Lance similarity, Neo4j) · transform/semantic (dbt, MetricFlow,
Cube) · feature/ML (Feast, Ray → MLflow) · AI/RAG (LlamaIndex, eval, LiteLLM/Ollama) · governance/quality
(DataHub, Soda, Ranger) · streaming (Redpanda, Debezium CDC).

Full scope: `docs/backlog.md` → B81 (Linear EMA-71). Each notebook must **run end-to-end** — that is the
test (DoD): the per-format set is self-contained; the stack-layer set runs against the live mesh.

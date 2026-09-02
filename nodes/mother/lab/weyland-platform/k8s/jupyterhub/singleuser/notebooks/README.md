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

### Stack layers — storage & versioning
| Notebook | Layer | Focus |
|---|---|---|
| `10_storage_lakefs.ipynb` | **lakeFS** (git-for-data) | zero-copy branch / commit / diff / merge / log + commit-id time-travel over the `music` repo — scratch-branch-only, self-cleaning |
| `11_storage_nessie_iceberg.ipynb` | **Nessie + Iceberg** | table-level versioning: snapshots, hidden partitioning, schema evolution, atomic commits; Nessie git-like catalog branching; commit-hash time-travel via `StaticTable` — reads `dbt.mart_*` read-only, writes a scratch `nb_demo` namespace, self-cleaning |

Both run against the **live** mesh. `10` versions *objects* (whole-lake, format-agnostic);
`11` versions *tables* (Iceberg snapshots, catalogued by Nessie) — they stack, and each
notebook explains where it sits relative to the other.

### Stack layers — query & federation
| Notebook | Layer | Focus |
|---|---|---|
| `20_query_trino_federation.ipynb` | **Trino** (federated SQL) | catalog/schema discovery; a real cross-catalog join — lakehouse eval scores (`iceberg.eval`) ⋈ operational eval results (`postgresql.public`) in one query; predicate + column pushdown via `EXPLAIN`. Read-only |
| `21_query_duckdb_gizmosql.ipynb` | **DuckDB** two ways | **embedded** DuckDB over lakeFS Parquet (httpfs, window fns, projection pushdown) + true zero-copy Arrow interop (polars↔arrow↔duckdb, identical buffer address); **served** via GizmoSQL Arrow Flight SQL (ADBC) over the persisted silver base tables (USDA relational JOINs). Read-only |
| `22_query_tier2_native.ipynb` | **6 Tier-2 stores**, native clients | one native client per engine — ClickHouse (`clickhouse-connect`, columnar OLAP) · Cassandra (`cassandra-driver`, wide-column) · MongoDB (`pymongo`, document) · CockroachDB (`psycopg`, distributed SQL) · TimescaleDB (`psycopg`, hypertable/time-series) · MySQL (`PyMySQL`, relational OLTP) — each with a real read on hydrated data + its niche. Read-only |

Only three Trino catalogs are wired here — **`iceberg`** (Nessie/Iceberg lakehouse on MinIO), **`postgresql`**
(the operational eval/operator DB), and **`system`**. The Tier-2 stores (ClickHouse/Cassandra/Mongo/Cockroach/
Timescale/MySQL) are **not** Trino connectors — they're queried by their **native clients** in `22`. Trino is the
distributed-federation half of the query layer; DuckDB/GizmoSQL (`21`) is the single-node OLAP half; `22` is the
per-engine native half. **That completes the query/federation wave.**

### Stack layers — vector & graph
| Notebook | Store | Focus |
|---|---|---|
| `30_vector_qdrant.ipynb` | **Qdrant** (served vector DB) | collection discovery + real vector config; semantic ANN (seeded from a stored vector); payload-filtered search; HNSW/quantization tuning. Read-only |
| `31_vector_weaviate.ipynb` | **Weaviate** (served, schema+hybrid) | **the U16 deliverable** (replaces the dropped Weaviate UI) — class/object browse, vector `near_vector`, BM25 keyword, hybrid (α), raw GraphQL. Read-only |
| `32_vector_lancedb.ipynb` | **LanceDB** (embedded) | opens the lakeFS-backed Lance tables directly (no server), IVF_PQ ANN vs exact cosine, contrasted with served Qdrant/Weaviate and Lance-the-format (`04`). Read-only |
| `33_graph_neo4j.ipynb` | **Neo4j** (graph) | live schema discovery, multi-hop Cypher traversal, degree/co-listen aggregation, GDS-if-present (graceful when absent). Read-only |

Served vector stores (Qdrant/Weaviate) vs embedded (LanceDB, reading Lance from lakeFS) vs graph (Neo4j).
Qdrant/Weaviate are open/anonymous; LanceDB reuses the lakeFS creds; Neo4j needs `NEO4J_PASSWORD`.

### Stack layers — *coming next* (B81 waves 5+)
transform/semantic (Qdrant, **Weaviate** [U16], Lance similarity, Neo4j) · transform/semantic (dbt, MetricFlow, Cube)
· feature/ML (Feast, Ray → MLflow) · AI/RAG (LlamaIndex, eval, LiteLLM/Ollama) · governance/quality (DataHub,
Soda, Ranger) · streaming (Redpanda, Debezium CDC).

Full scope: `docs/backlog.md` → B81 (Linear EMA-71). Each notebook must **run end-to-end** — that is the
test (DoD): the per-format set is self-contained; the stack-layer set runs against the live mesh.

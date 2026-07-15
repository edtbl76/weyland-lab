# Flow — LanceDB (embedded vector store + viewer + event-sync)

LanceDB is the odd one among the vector stores: **embedded** (a library, no server), **Lance-format-native**,
and backed by **object storage** (the lakeFS S3 gateway) rather than a pod's memory. That architecture makes
three things non-obvious — how you query it, how you browse it, and how the browse UI stays fresh. See
[query/lancedb.md](../query/lancedb.md) + [runbooks/datasets-hydration.md](../runbooks/datasets-hydration.md).

```mermaid
flowchart TB
  subgraph BUILD["build (Dagster)"]
    BV["_build_vectors<br/>(shared with Qdrant/Weaviate)<br/>z-score numeric · bge text"]
    LOAD["datasets_&lt;dom&gt;_lancedb_load<br/>write Lance tables + ANN index"]
    BV --> LOAD
  end

  STORE[("lakeFS S3 gateway<br/>s3://&lt;repo&gt;/main/lancedb/&lt;table&gt;<br/>SOURCE OF TRUTH")]
  LOAD -->|"lancedb.connect(s3://…)"| STORE

  subgraph QUERY["query (embedded — no server)"]
    HELPER["scripts/lancedb_query.py<br/>+ cookbook · in-process ANN"]
    DH["DataHub — emit_lancedb<br/>(catalog: schema + lineage)"]
  end
  STORE -->|"open_table().search(v)"| HELPER
  STORE --> DH

  subgraph VIEW["browse (Lance Data Viewer — filesystem-only)"]
    SENSOR["lancedb_sync_sensor<br/>(fires on load materialization)"]
    SYNCJOB["lancedb-sync Job<br/>mc mirror S3 → PVC"]
    PVC[("lancedb-viewer PVC")]
    VIEWER["Lance Data Viewer<br/>lancedb.weyland.lab (RO)"]
  end
  LOAD -.->|"materialized"| SENSOR
  SENSOR -->|"create Job (RBAC)"| SYNCJOB
  STORE -->|"mc mirror"| SYNCJOB
  SYNCJOB --> PVC
  PVC -->|"mount /data RO"| VIEWER

  classDef truth fill:#2d6a4f,stroke:#95d5b2,color:#fff;
  class STORE truth;
```

**Why each hop exists:**

- **Query = in-process.** No server/port/JDBC — you connect to the storage and search in the same process
  (`scripts/lancedb_query.py`, or the cookbook). Same as how the Qdrant/Weaviate *dataset* vectors are queried
  (via clients, not a served API). DataHub sees it via the `emit_lancedb` custom emitter (no native source —
  it's not a server DB).
- **Browse needs a mirror.** [Lance Data Viewer](https://github.com/lance-format/lance-data-viewer) is a nice
  read-only web UI, but it's **filesystem-only** (mounts a folder at `/data`, no S3). So a job `mc mirror`s the
  Lance tables from the lakeFS gateway → a PVC the viewer mounts read-only. lakeFS stays the source of truth;
  the PVC is a disposable read replica.
- **Sync is event-triggered, not polled.** The tables change *only* when a `lancedb_load` asset runs — so a
  Dagster **multi-asset sensor** watches those two assets and, on materialization, launches the mirror Job
  (created from the `lancedb-sync` CronJob template, via cross-namespace RBAC). The 6h CronJob remains a
  safety-net backfill. So: **load → sensor → mirror → fresh viewer**, no polling loop.

**Gotcha:** the sync Job runs in `data-mesh` and needs `lakefs-creds` there — that secret lives in `weyland`, so
it's copied into `data-mesh` **imperatively** (not in git). If `data-mesh` is rebuilt, recreate it
(`kubectl get secret lakefs-creds -n weyland -o yaml | sed 's/namespace: weyland/namespace: data-mesh/' | kubectl apply -f -`).

## Sequence

Build → in-process query, and the event-triggered mirror that keeps the browse UI fresh. Demo: [demos/lancedb.md](../demos/lancedb.md).

```mermaid
sequenceDiagram
    actor User
    participant Dagster as Dagster
    participant UC as dagster-user-code
    participant Lake as lakeFS S3 gateway<br/>(s3://<repo>/main/lancedb)
    participant Sensor as lancedb_sync_sensor
    participant Job as lancedb-sync Job
    participant PVC as lancedb-viewer PVC
    participant Viewer as Lance Data Viewer<br/>(lancedb.weyland.lab)

    User->>Dagster: materialize datasets_<dom>_lancedb_load
    Dagster->>UC: launchRun
    UC->>UC: _build_vectors (z-score numeric / bge text)
    UC->>Lake: write Lance tables + ANN index (>=2000 rows)
    UC->>Dagster: emit_lancedb (DataHub catalog)
    UC-->>Sensor: materialization event
    Sensor->>Job: create Job (cross-ns RBAC)
    Lake->>Job: mc mirror Lance tables
    Job->>PVC: write /data
    PVC->>Viewer: mount /data (read-only)
    User->>Lake: lancedb.connect(s3://...).open_table().search(v)
    Lake-->>User: nearest rows (in-process)
```

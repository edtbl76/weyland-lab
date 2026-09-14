# Flow: Vector stores — OFF hydration + quality + observability (B78)

Bounded read → embed → load into three vector backends, kept under the pod memory ceiling by a projected + capped read
(the whole-file read used to OOM). U13: the embed step runs bge-small on raw ONNX Runtime now — byte-equivalent, no re-hydration.

```mermaid
sequenceDiagram
    autonumber
    participant D as Dagster (launchRun)
    participant P as silver Parquet (lakeFS / MinIO)
    participant E as bge-small embedder<br/>(ONNX Runtime, U13)
    participant V as Vector store<br/>(Qdrant · Weaviate · LanceDB)
    participant PR as Prometheus + Grafana
    D->>P: read_capped (projected + capped, ~18.6 MB peak)
    P-->>D: bounded rows
    D->>E: embed texts (batched)
    E-->>D: 384-dim vectors
    D->>V: load (idempotent keyed upserts)
    D->>D: vectors_present_and_nondegenerate check (passed=True)
    V-->>PR: lancedb-exporter /metrics · collection_points · object_count
    Note over PR: Grafana "Vector Stores" board + LancedbExporterDown / LancedbRepoUnreachable alerts
```

Demo: [demos/vector-stores.md](../demos/vector-stores.md).

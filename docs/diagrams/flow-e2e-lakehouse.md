# Flow (E2E) — Lakehouse: land → silver → Iceberg gold → dbt marts → BI

Cross-system thread of three validated component flows —
[flow-datasets-lakehouse](flow-datasets-lakehouse.md) → [flow-flink](flow-flink.md)'s sibling
[dbt] → [flow-semantic-consumption](flow-semantic-consumption.md) — plus the Tier-2 hydration fan-out off
silver. One dataset walked bronze → silver → gold → tested marts → governed metric. Demo:
[../demos/lakehouse-e2e.md](../demos/lakehouse-e2e.md).

```mermaid
sequenceDiagram
    actor Op as Operator (mother)
    participant DAG as Dagster<br/>(dagster.weyland.lab)
    participant Src as public source<br/>(HF / WHO / FMA)
    participant Lake as lakeFS<br/>(raw + parquet/arrow/avro/lance)
    participant Ice as Iceberg / Nessie<br/>(gold + iceberg.dbt.*)
    participant Trino as Trino
    participant DBT as dbt-trino<br/>(weyland_dbt_assets)
    participant T2 as Tier-2 stores<br/>(ClickHouse / Cassandra)
    participant Cube as Cube SQL API<br/>(:15432, trino-noauth)
    participant LD as Lightdash / Superset

    Op->>DAG: materialize land asset ({"force": true})
    DAG->>Src: fetch source files (freshness-gated)
    DAG->>Lake: put raw/<table> (BRONZE)
    Op->>DAG: run weyland_datasets_<domain>_transform_job
    DAG->>Lake: write parquet / arrow / avro / lance (SILVER)
    DAG->>Ice: create/overwrite datasets_<domain>.<table> (GOLD)
    T2->>Lake: hydrate from silver parquet (s3() / lakeFS)
    Op->>DAG: materialize weyland_dbt_assets
    DAG->>Trino: dbt build (compiled SQL)
    Trino->>Ice: read gold (sources)
    Trino->>Ice: CREATE TABLE iceberg.dbt.mart_* (Trino writes)
    Op->>Cube: SELECT dim, MEASURE(metric) FROM cube
    Cube->>Trino: compiled SQL via trino-noauth proxy
    Trino->>Ice: read mart_*
    Trino-->>Cube: rows
    Cube-->>Op: governed metric value
    Op->>LD: open explore → chart over same marts
```

**Seams made explicit:** land/transform own bronze→silver→gold ([datasets-lakehouse](../demos/datasets-lakehouse.md));
dbt owns gold→marts, Trino does the writing ([dbt](../demos/dbt.md)); Cube/MetricFlow/Lightdash/Superset serve the
marts as metrics-defined-once ([semantic-consumption](../demos/semantic-consumption.md)). Tier-2 stores read the
**same silver parquet** in parallel — an independent consumer, not a step in the mart chain.

# Flow — Datasets lakehouse (bronze → silver → gold → checks → stores)

The datasets platform (`datasets_lib`, B72/B75). A domain (music, health) is a `DomainConfig` fed through
three asset factories: **transform → asset-checks → store-load**. See
[runbooks/datasets-lake.md](../runbooks/datasets-lake.md) and
[runbooks/datasets-hydration.md](../runbooks/datasets-hydration.md).

```mermaid
flowchart TB
  subgraph SRC["public sources"]
    HF["HuggingFace"]
    CDC["CDC — XPT / Socrata"]
    WHO["WHO GHO — JSON"]
    FMA["FMA zip · CSV · gz"]
  end

  LAND["per-dataset LAND assets<br/>music ×12 · health ×8<br/>freshness-gated · RefreshConfig.force"]
  RAW[("lakeFS raw/ — BRONZE<br/>csv · csv.gz · xpt · json")]

  subgraph LIB["datasets_lib — one DomainConfig, three factories"]
    T["build_transform_assets<br/>brokered · serialized · per-file<br/>reader dispatch · name-normalize · null-coerce · size-guard"]
    C["build_asset_checks<br/>@asset_check gate<br/>no_failures · expected_tables · valid_column_names"]
    L["build_store_load_assets<br/>silver Parquet → store, batched"]
  end

  subgraph SILVER["SILVER — lakeFS"]
    PQ["parquet"]
    AR["arrow"]
    AV["avro"]
    LN["lance"]
  end
  GOLD[("Iceberg GOLD — Nessie<br/>datasets_&lt;domain&gt;.&lt;table&gt; per-file")]

  subgraph STORES["Tier-2 stores — silver Parquet → store"]
    DONE["DONE (10): MySQL · TimescaleDB · MongoDB · CockroachDB · Cassandra<br/>ClickHouse (native s3) · OpenSearch · Neo4j (graph)<br/>Qdrant + Weaviate (vector — z-scored features / bge text)"]
    PLAN["NEXT: Feast"]
  end

  DH["DataHub<br/>emit_file_dataset · iceberg source"]

  HF --> LAND
  CDC --> LAND
  WHO --> LAND
  FMA --> LAND
  LAND --> RAW
  RAW --> T
  T --> PQ
  T --> AR
  T --> AV
  T --> LN
  T --> GOLD
  PQ -. commit .-> RAW
  T --> C
  PQ --> L
  C -. gates .-> L
  L --> DONE
  L -. next .-> PLAN
  PQ --> DH
  AV --> DH
  LN --> DH
  GOLD --> DH
```

**Streaming sink (B1.5):** beyond the batch store hydration, silver also feeds the **streaming** tier — the
`datasets_<dom>_stream_produce` assets replay stream-shaped silver (lastfm, big_five, brfss, nhis) as **Avro
events** into Redpanda topics, and Debezium streams Postgres CDC alongside. That's a separate flow (events, not
tables): [flow-streaming.md](flow-streaming.md) · [flow-cdc.md](flow-cdc.md).

**Layers:** land (bronze) → transform (silver + gold) → quality gate → store hydration. Cleaning
(name-normalize, null-coerce, delimiter fixes) lives in the transform/land; the checks *validate* (they
don't mutate); a bad silver blocks hydration via the `no_failures` check on parquet.

## Sequence

The runtime order for one dataset through the three factories. Demo: [demos/datasets-lakehouse.md](../demos/datasets-lakehouse.md).

```mermaid
sequenceDiagram
    actor User
    participant Dagster as Dagster<br/>(dagster.weyland.lab)
    participant UC as dagster-user-code
    participant Src as public source
    participant Lake as lakeFS
    participant Ice as Iceberg / Nessie
    participant DH as DataHub

    User->>Dagster: materialize LAND asset<br/>(config {"force": true})
    Dagster->>UC: launchRun (land, freshness-gated)
    UC->>Src: fetch source files
    UC->>Lake: put raw/<table>/<file> (BRONZE)
    User->>Dagster: run weyland_datasets_<domain>_transform_job
    Dagster->>UC: launchRun (serialized, max_concurrent=1)
    UC->>Lake: read raw/<table>
    par one asset per format (broker)
        UC->>Lake: write parquet / arrow / avro / lance (SILVER)
    and gold
        UC->>Ice: overwrite datasets_<domain>.<table> (GOLD)
    end
    UC->>Lake: _commit (version lakeFS)
    UC->>UC: build_asset_checks (no_failures gate on parquet)
    UC->>Lake: build_store_load_assets → Tier-2 stores (batched)
    UC->>DH: emit_file_dataset (silver) + iceberg source (gold)
```

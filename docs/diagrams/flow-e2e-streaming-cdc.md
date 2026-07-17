# Flow (E2E) — Streaming + CDC: produce / Debezium → Redpanda → Flink → Iceberg → Trino

Cross-system thread of [flow-streaming](flow-streaming.md) + [flow-cdc](flow-cdc.md) into
[flow-flink](flow-flink.md): a bounded Avro replay and a continuous WAL tail both land on Redpanda, Flink's four
jobs stream-process them, and the SQL jobs write Iceberg on the same Nessie catalog Trino reads. Demo:
[../demos/streaming-cdc-e2e.md](../demos/streaming-cdc-e2e.md).

```mermaid
sequenceDiagram
    actor Op as Operator (mother)
    participant DAG as Dagster stream_produce
    participant MB as musicbrainz-postgres
    participant DBZ as Debezium (Kafka Connect)
    participant SR as Redpanda Schema Registry
    participant RP as Redpanda topics<br/>(datasets.* + cdc.*)
    participant FOP as Flink K8s Operator
    participant JM as Flink session cluster<br/>(weyland-flink) + PyFlink app
    participant Ice as Iceberg / Nessie<br/>(analytics.* + cdc_demo_live)
    participant Trino as Trino

    Op->>DAG: materialize datasets_*_stream_produce
    DAG->>SR: register Avro schema (subject topic-value)
    DAG->>RP: produce datasets.music.lastfm / health.brfss (bounded)
    Op->>DBZ: register musicbrainz-cdc connector
    MB->>DBZ: WAL logical-decode (pgoutput slot)
    DBZ->>SR: register Avro schema (Confluent wire format)
    DBZ->>RP: emit cdc.musicbrainz.public.cdc_demo (op/before/after)
    FOP->>JM: submit FlinkSessionJobs (RTA / CDC / health) + PyFlink app
    JM->>SR: fetch Avro schema by id
    JM->>RP: consume datasets.* / cdc.* topics
    JM->>Ice: SQL jobs write analytics.trending_artists / datasets_music.cdc_demo_live
    JM->>RP: Java/PyFlink write analytics.health.state_risk / music.artist_tier
    Op->>Trino: SELECT ... FROM iceberg.analytics.*
    Trino->>Ice: read Flink-written Iceberg tables
    Trino-->>Op: rows
```

**Seams made explicit:** streaming/CDC own producing the source topics
([streaming](../demos/streaming.md) / [cdc](../demos/cdc.md)); Flink owns consuming them into Iceberg + Kafka
([flink](../demos/flink.md)). RTA + PyFlink read the **bounded** `datasets.music.lastfm`; the CDC job reads the
**continuous** `cdc.*` topic; health reads `datasets.health.brfss`. Trino closes the loop by querying the Iceberg
that the two SQL jobs wrote.

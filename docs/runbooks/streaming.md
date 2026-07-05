# Runbook — Streaming tier (Redpanda + Avro producer + Debezium CDC)

The B1.5 streaming data plane. **Redpanda** = the Kafka-wire broker (single-node, KRaft, built-in Schema
Registry); an **Avro producer** replays stream-shaped silver into topics; **Debezium** (on Kafka Connect)
streams Postgres changes. Manifests in `k8s/data-mesh/` (`redpanda.yaml`, `kafka-connect.yaml`), producer in
`services/weyland-dagster/weyland_pipeline/assets/datasets_lib/streaming_producer.py`. Diagrams:
[../diagrams/flow-streaming.md](../diagrams/flow-streaming.md) · [../diagrams/flow-cdc.md](../diagrams/flow-cdc.md).

## Redpanda

- **Deploy:** `redpanda.yaml` — single-node StatefulSet, ns `data-mesh`, `--overprovisioned` (disables Seastar
  CPU busy-poll — **mandatory** on the shared/tight node), RF=1, 10Gi PVC. **Sidecar OFF** (Kafka is opaque
  long-lived TCP; a meshed client → non-meshed broker is fine under PERMISSIVE, and it dodges the
  half-open-behind-Envoy stall we hit with neo4j Bolt). Ports: 9092 kafka · 8081 schema-registry · 8082
  http-proxy · 9644 admin · 33145 rpc.
- **Console UI:** `redpanda.weyland.lab` (forward-auth) — topics, schemas, consumer groups, **decoded** Avro
  message browse (rpk shows raw binary; Console decodes against the registry).
- **Bootstrap for in-cluster clients:** `redpanda.data-mesh.svc.cluster.local:9092`.
- **Admin (rpk, in-pod):**
  ```
  kubectl -n data-mesh exec redpanda-0 -- rpk cluster health
  kubectl -n data-mesh exec redpanda-0 -- rpk topic list
  kubectl -n data-mesh exec redpanda-0 -- rpk topic consume <topic> --num 1
  kubectl -n data-mesh exec redpanda-0 -- curl -s localhost:8081/subjects      # registered Avro schemas
  ```

## Avro producer (event replay)

- **Asset:** `datasets_<domain>_stream_produce` (in the `datasets_<domain>_stores` group → runs in the hydrate
  job). Config = `stream_allow = {dataset: {"key": col_or_None, "cap": int_or_None}}` on `DomainConfig`.
- **What it does:** replays stream-shaped silver → Avro events into `datasets.<domain>.<dataset>` (3 partitions,
  RF=1), registering the schema via confluent-kafka's `AvroSerializer` (**Confluent wire format** — magic byte +
  schema id, so Console/consumers decode it). **Bounded** replay (cap) — a demo/"Avro in motion", not a bulk
  dump. Loaded: lastfm (key=user_id, cap 100k), big_five, brfss, nhis.
- **Env (dagster user-code):** `REDPANDA_BOOTSTRAP`, `SCHEMA_REGISTRY_URL`.

## DataHub catalog

- **Source-of-record:** `k8s/data-mesh/datahub-ingestion/kafka.recipe.yaml` — native `kafka` source pointed at
  Redpanda (bootstrap + schema_registry_url), `topic_patterns` fenced to `^datasets\..*`. No auth (Redpanda is
  plaintext on the LAN). UI-configured; **02:15 daily** ([../schedules.md](../schedules.md)). Catalogs topics +
  their Avro schemas → closed the last B65 target. Points at OUR Redpanda, NOT DataHub's internal Kafka.

## Debezium CDC (Kafka Connect)

- **Worker:** `kafka-connect.yaml` — `quay.io/debezium/connect` Deployment, ns `data-mesh`, sidecar off,
  internal config/offset/status topics **RF=1** (single-node), REST on 8083. Connectors ARE Connect plugins, so
  CDC = this worker + a registered Postgres connector.
- **Source DB:** **musicbrainz-postgres** — chosen because it's **isolated** (nothing depends on it) and
  **reproducible** (re-importable from the mbdump). **NEVER the core weyland-postgres** — a stalled slot bloating
  WAL there would brick the whole control plane.
- **Source prep** (in `musicbrainz-postgres.yaml` args): `wal_level=logical` (needs a restart) +
  **`max_slot_wal_keep_size=4GB`** (the seatbelt — a stalled slot self-invalidates instead of filling the disk →
  worst case "CDC stops", never "DB down"). Per-table: `ALTER TABLE … REPLICA IDENTITY FULL` for a complete
  `before` image (default logs PK only).
- **Register a connector** (REST; `jq -n --arg pw` escapes the password):
  ```
  PW=$(kubectl -n data-mesh get secret musicbrainz-postgres-secret -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
  jq -n --arg pw "$PW" '{name:"musicbrainz-cdc",config:{"connector.class":"io.debezium.connector.postgresql.PostgresConnector","database.hostname":"musicbrainz-postgres.data-mesh.svc.cluster.local","database.port":"5432","database.user":"postgres","database.password":$pw,"database.dbname":"musicbrainz_db","topic.prefix":"cdc.musicbrainz","plugin.name":"pgoutput","slot.name":"debezium_cdc","publication.name":"debezium_pub","publication.autocreate.mode":"filtered","table.include.list":"public.cdc_demo","snapshot.mode":"initial","tombstones.on.delete":"false"}}' | kubectl -n data-mesh exec -i deploy/kafka-connect -- curl -s -XPOST -H "Content-Type: application/json" --data-binary @- localhost:8083/connectors
  kubectl -n data-mesh exec deploy/kafka-connect -- curl -s localhost:8083/connectors/musicbrainz-cdc/status
  ```
- **Topic:** `<topic.prefix>.<schema>.<table>` = `cdc.musicbrainz.public.cdc_demo`. Events carry the Debezium
  envelope (`op`=r/c/u/d, `before`, `after`, `source`.lsn/txId).

## Avro converter for CDC

The `debezium/connect` image lacks `io.confluent.connect.avro.AvroConverter`. `kafka-connect.yaml` adds it via
an **initContainer** copying `confluentinc/cp-kafka-connect`'s `/usr/share/java/kafka-serde-tools/` (the
self-contained bundle) into an emptyDir mounted at `/kafka/connect/confluent-avro` (on plugin.path →
plugin-isolated load). **GOTCHA:** use `cp -r`, NOT `cp -a` — the emptyDir mount rejects preserve-times
("Operation not permitted") → `-a` exits non-zero → `Init:Error`. Then set converters at the **connector** level
(`key/value.converter=io.confluent.connect.avro.AvroConverter` + `.schema.registry.url`) via a `PUT
/connectors/<name>/config` — leaving the worker's internal topics JSON. New events are Avro; old JSON messages
stay in the topic (mixed history).

## Gotchas (all confirmed live)

- **Single-node → RF=1 everywhere** — Redpanda topics (producer 3 partitions/RF1), Connect internal topics
  (`*_STORAGE_REPLICATION_FACTOR=1`), Debezium output. Default RF=3 fails to create.
- **Debezium 3.0.0.Final works on PostgreSQL 18** (the version watch-point cleared).
- **`pgoutput`** = the built-in logical-decoding plugin (no wal2json install). `publication.autocreate.mode=filtered`
  scopes the publication to the captured table (not `FOR ALL TABLES`).
- **Teardown discipline:** deleting a Debezium connector does **not** drop its replication slot — drop it
  manually or it keeps retaining WAL (the seatbelt bounds it, but clean up):
  `SELECT pg_drop_replication_slot('debezium_cdc');`

## Pending follow-ons

Strimzi on-demand learning lane (single-node KRaft for the operator/CRD experience; temporarily 3-broker to
observe ISR — which Redpanda's Raft-per-partition can't teach) + a **KEDA consumer-lag scaler** (the canonical
KEDA+Kafka pattern — scale a consumer on `datasets.*`/`cdc.*` lag). See memory `streaming-tier-redpanda-strimzi`.

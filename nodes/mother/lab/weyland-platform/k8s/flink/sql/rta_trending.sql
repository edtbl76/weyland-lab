-- B83 · RTA job — trending artists over the lastfm listen stream (Flink SQL).
-- Source: datasets.music.lastfm (Confluent-Avro via the Redpanda schema registry). Event time = the KAFKA RECORD
--   timestamp (lastfm has no per-play timestamp of its own; the producer's replay time is fine for "plays/window").
-- Sink: Iceberg analytics.trending_artists via the Nessie Iceberg-REST catalog → the SAME warehouse Trino/dbt use,
--   so it's instantly queryable in Trino/Superset and auto-cataloged by DataHub's iceberg source. S3FileIO → MinIO
--   uses the AWS_* env creds already on the pod.

SET 'pipeline.name' = 'rta-trending-artists';

-- Native NessieCatalog → Nessie's /api/v2 (the proven Trino path; the generic Iceberg REST client 403s on Nessie).
-- S3FileIO → MinIO via AWS_* env; warehouse = the same s3://warehouse Trino/dbt use, ref = main.
CREATE CATALOG nessie WITH (
  'type' = 'iceberg',
  'catalog-impl' = 'org.apache.iceberg.nessie.NessieCatalog',
  'uri' = 'http://nessie.data-mesh.svc.cluster.local:19120/api/v2',
  'ref' = 'main',
  'warehouse' = 's3://warehouse',
  'io-impl' = 'org.apache.iceberg.aws.s3.S3FileIO',
  's3.endpoint' = 'http://minio.minio.svc.cluster.local:9000',
  's3.path-style-access' = 'true'
);

CREATE DATABASE IF NOT EXISTS nessie.analytics;

CREATE TABLE IF NOT EXISTS nessie.analytics.trending_artists (
  window_start TIMESTAMP(3),
  window_end   TIMESTAMP(3),
  artist_name  STRING,
  plays        BIGINT,
  listeners    BIGINT
);

-- Kafka source (default in-memory catalog — not persisted in Iceberg).
CREATE TEMPORARY TABLE lastfm_src (
  user_id     STRING,
  artist_name STRING,
  event_time  TIMESTAMP(3) METADATA FROM 'timestamp',
  WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'datasets.music.lastfm',
  'properties.bootstrap.servers' = 'redpanda.data-mesh.svc.cluster.local:9092',
  'properties.group.id' = 'flink-rta-trending',
  'scan.startup.mode' = 'earliest-offset',
  -- BOUNDED: lastfm is a bounded REPLAY (not a live feed). Reading earliest→latest then stopping makes Flink emit
  -- a MAX watermark on end-of-input, so every tumbling window CLOSES and commits. Drop this line for a live stream.
  'scan.bounded.mode' = 'latest-offset',
  'format' = 'avro-confluent',
  'avro-confluent.url' = 'http://redpanda.data-mesh.svc.cluster.local:8081'
);

-- Tumbling window: plays + distinct listeners per artist → Iceberg (append). 1 MINUTE so windows FIRE on the
-- bounded replay (a 1h window wouldn't close — watermark stops at the last record's time). Widen for a live stream.
INSERT INTO nessie.analytics.trending_artists
SELECT
  window_start,
  window_end,
  artist_name,
  COUNT(*)                AS plays,
  COUNT(DISTINCT user_id) AS listeners
FROM TABLE(TUMBLE(TABLE lastfm_src, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
GROUP BY window_start, window_end, artist_name;

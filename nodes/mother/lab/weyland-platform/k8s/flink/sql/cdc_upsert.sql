-- B83 CDC job (Flink SQL) - Debezium CDC of musicbrainz public.cdc_demo -> Iceberg UPSERT (CONTINUOUS).
-- This is the flagship continuous job: a live source (Debezium emits a change event per INSERT/UPDATE/DELETE),
-- so the job runs forever, keeps the JM UI populated with slots/tasks, and is a real target for the flame graphs.
-- Sink is Iceberg v2 with upsert enabled -> the Flink Iceberg connector applies equality-deletes on the PK, so
-- the target table mirrors the source row-for-row (not an append log). Same native Nessie catalog as Trino/dbt.
SET 'pipeline.name' = 'cdc-cdc-demo-live';

-- Native NessieCatalog (/api/v2) - the proven path (generic Iceberg REST client 403s on Nessie). Same warehouse.
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

CREATE DATABASE IF NOT EXISTS nessie.datasets_music;

-- Iceberg v2 upsert target (equality-deletes keyed on id). The live mirror of public.cdc_demo.
CREATE TABLE IF NOT EXISTS nessie.datasets_music.cdc_demo_live (
  id   INT,
  note STRING,
  PRIMARY KEY (id) NOT ENFORCED
) WITH (
  'format-version' = '2',
  'write.upsert.enabled' = 'true'
);

-- Debezium source: the debezium-avro-confluent format decodes the op/before/after envelope into a Flink
-- changelog stream (+I / -U / +U / -D). The PK makes it an upserting changelog. Continuous (no bounded mode).
CREATE TEMPORARY TABLE cdc_src (
  id   INT,
  note STRING,
  PRIMARY KEY (id) NOT ENFORCED
) WITH (
  'connector' = 'kafka',
  'topic' = 'cdc.musicbrainz.public.cdc_demo',
  'properties.bootstrap.servers' = 'redpanda.data-mesh.svc.cluster.local:9092',
  'properties.group.id' = 'flink-cdc-cdc-demo',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'debezium-avro-confluent',
  'debezium-avro-confluent.url' = 'http://redpanda.data-mesh.svc.cluster.local:8081'
);

INSERT INTO nessie.datasets_music.cdc_demo_live SELECT id, note FROM cdc_src;

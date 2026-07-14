# weyland-flink — Flink 1.20 session-cluster image (B83, streaming-processing tier).
# Base + the connectors/formats the SQL and code jobs need:
#   - Iceberg Flink runtime (REST catalog → Nessie /iceberg) + iceberg-aws-bundle (S3FileIO → MinIO warehouse)
#   - Kafka SQL connector + Confluent-Avro registry format (reads the datasets.* Avro + cdc.* Debezium topics)
#   - the built-in S3 filesystem (Hadoop) plugin for checkpoints/savepoints
# Build on mother + `ctr import` into k3s (single node), like the dagster/jupyter images.
#
# VERSIONS = the validate-points. If a curl 404s at build, the coordinate/version is wrong — bump the ARG.
#   Flink 1.20.1 · Iceberg 1.7.1 · Kafka connector 3.3.0-1.20 · avro-confluent format tracks Flink (1.20.1).
FROM flink:1.20.1-java17

ARG ICEBERG_VER=1.7.1
ARG KAFKA_CONN_VER=3.3.0-1.20
ARG FLINK_VER=1.20.1
ARG MAVEN=https://repo1.maven.org/maven2

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Enable the built-in S3 filesystem (Hadoop) as a plugin — for state.checkpoints.dir / savepoints on s3://.
# The jar ships in /opt/flink/opt; a plugin dir isolates its classpath.
RUN mkdir -p /opt/flink/plugins/s3-fs-hadoop && \
    cp /opt/flink/opt/flink-s3-fs-hadoop-*.jar /opt/flink/plugins/s3-fs-hadoop/

# Connectors + formats onto the SQL classpath (/opt/flink/lib).
# NOTE flink-shaded-hadoop-2-uber: Iceberg's FlinkCatalogFactory always does `new hadoop.conf.Configuration()` when
# creating ANY catalog (even REST + S3FileIO), so Hadoop core must be on the MAIN classpath — the s3-fs-hadoop
# plugin's Hadoop is isolated in a plugin classloader and doesn't count. This uber jar is package-shaded to coexist
# with Flink (only org.apache.hadoop stays un-relocated), so it's the safe single-jar fix.
ARG HADOOP_UBER_VER=2.8.3-10.0
RUN set -eux; cd /opt/flink/lib; \
    curl -fLO ${MAVEN}/org/apache/iceberg/iceberg-flink-runtime-1.20/${ICEBERG_VER}/iceberg-flink-runtime-1.20-${ICEBERG_VER}.jar; \
    curl -fLO ${MAVEN}/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VER}/iceberg-aws-bundle-${ICEBERG_VER}.jar; \
    curl -fLO ${MAVEN}/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONN_VER}/flink-sql-connector-kafka-${KAFKA_CONN_VER}.jar; \
    curl -fLO ${MAVEN}/org/apache/flink/flink-sql-avro-confluent-registry/${FLINK_VER}/flink-sql-avro-confluent-registry-${FLINK_VER}.jar; \
    curl -fLO ${MAVEN}/org/apache/flink/flink-shaded-hadoop-2-uber/${HADOOP_UBER_VER}/flink-shaded-hadoop-2-uber-${HADOOP_UBER_VER}.jar

USER flink

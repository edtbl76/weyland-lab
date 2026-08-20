---
id: data-serialization-formats
tags: [reference, data, backend, network]
surfaces-at: [functional-design, application-design]
related: [data-pipelines, kafka, grpc, openapi-specification, schema-evolution, data-lake]
complexity: beginner
---

# Data Serialization Formats

## What It Is
The encoding formats used to convert in-memory data structures into bytes for storage, transmission, or inter-process communication. Format choice affects performance (serialization/deserialization speed, payload size), schema enforcement, human readability, language compatibility, and schema evolution capabilities. Different formats are optimal for different contexts — no single format is best everywhere. Choosing the wrong format leads to unnecessary storage costs, poor query performance, schema drift, and tight coupling between producers and consumers.

## When to Apply
- Choosing a format for data pipeline storage, API payloads, message queue messages, or database exports
- Designing inter-service communication
- Optimizing analytical query performance on large datasets

## Key Concepts

**JSON**:
- Human-readable, universally supported, schema-optional
- Verbose — high byte overhead; repeated field names in every record
- No binary types; loose typing (numbers can lose precision)
- Best for: REST API payloads, configuration, human-inspected data, low-volume inter-service messages

**Parquet**:
- Columnar binary format; highly compressed; optimized for analytical reads
- Read a column across millions of rows with minimal I/O — dramatically faster and cheaper for analytics
- Immutable once written; not suitable for streaming writes
- Best for: Data lake storage, analytical datasets, ML training data, Athena/Spark/BigQuery inputs
- The default format for data lake silver/gold layers

**Avro**:
- Row-oriented binary format; compact; requires a schema
- Schema is embedded in or registered with the message — enables schema evolution
- Optimal for streaming/CDC: efficient row-by-row writes, Kafka-native via Schema Registry
- Best for: Kafka messages, CDC event streams, write-heavy ingestion pipelines

**Protobuf (Protocol Buffers)**:
- Binary format; smallest payload size; requires a .proto schema definition
- Generated client code in multiple languages — strong typing, no runtime schema parsing
- Excellent for RPC (gRPC uses Protobuf natively); less tooling for ad-hoc data exploration
- Best for: gRPC service contracts, high-throughput internal service communication

**ORC (Optimized Row Columnar)**:
- Columnar binary format; similar to Parquet; better compression in some cases
- Native to the Hive/Hadoop ecosystem
- Best for: Hive workloads; prefer Parquet for Spark/Iceberg/Athena

**CSV**:
- Human-readable, universal, no schema enforcement
- Fragile — delimiter conflicts, encoding issues, no type information
- Best for: Data exchange with non-technical stakeholders, legacy system integration; avoid for internal systems

**Format Selection Guide**:
- REST APIs → JSON
- Kafka messages → Avro (with Schema Registry)
- gRPC services → Protobuf
- Data lake storage → Parquet (columnar analytics) or Avro (streaming ingestion)
- ML training data → Parquet

## In Practice
Method uses JSON for REST API payloads, Avro with Confluent Schema Registry for Kafka messages, Protobuf for gRPC services, and Parquet for all data lake storage. CSV is accepted only for external data exchange and immediately converted to Parquet on ingestion.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Serialization Formats**: Parquet for storage, Avro for streaming, Protobuf for RPC, JSON for APIs. Never store large datasets as JSON — columnar Parquet is 5-10x smaller and 10-100x faster for analytical queries. Use Avro with Schema Registry for Kafka — the schema is registered and versioned, enabling evolution without breaking consumers. Protobuf's generated clients enforce the contract at compile time — ideal for gRPC. CSV is a data exchange format, not a storage format — convert to Parquet immediately on ingestion. → `engineering-knowledge-repository/data-serialization-formats.md`

## Related Entries
- [Data Pipelines](data-pipelines.md) — format selection affects ingestion throughput and storage cost throughout the pipeline
- [Kafka](kafka.md) — Kafka messages use Avro with Schema Registry as the standard serialization format
- [gRPC](grpc.md) — gRPC uses Protobuf as its native serialization format
- [OpenAPI Specification](openapi-specification.md) — OpenAPI defines JSON/YAML schema for REST API payloads
- [Schema Evolution](schema-evolution.md) — format choice determines what schema changes are safe to make
- [Data Lake](data-lake.md) — Parquet is the standard storage format for data lake analytical layers

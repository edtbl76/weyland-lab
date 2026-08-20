---
id: data-lake
tags: [pattern, data, cloud, backend]
surfaces-at: [application-design, infrastructure-design]
related: [data-warehouse, data-pipelines, spark, data-quality, data-catalog, data-lineage, data-archiving]
complexity: intermediate
---

# Data Lake

## What It Is
A centralized repository that stores raw data at any scale — structured, semi-structured, and unstructured — in its native format until it is needed. Unlike data warehouses that require predefined schemas, data lakes use schema-on-read: the schema is applied when data is queried, not when it is stored. Cloud object storage (S3, GCS, ADLS) is the foundation. Data lakes are cheap for storage, flexible for ingestion, and the natural landing zone for all organizational data before it is transformed for specific use cases.

## When to Apply
- Storing raw data from multiple source systems before knowing all downstream use cases
- ML and data science workloads that need access to raw, unprocessed data
- Long-term data retention for compliance and reprocessing
- As the raw storage layer beneath a data warehouse or lakehouse architecture

## Key Concepts
- **Schema-on-Read**: Data is stored as-is (JSON, CSV, Parquet, Avro, images, logs). The schema is defined at query time by the consumer. Maximum ingestion flexibility; discovery and governance require effort
- **Zones / Layers**: Organize the lake into processing zones:
  - *Raw / Bronze*: Exact copy of source data, immutable, never modified
  - *Cleaned / Silver*: Validated, deduplicated, standardized — still near-raw
  - *Curated / Gold*: Business-ready, aggregated, ready for analytics and ML
- **Open Table Formats**: Add ACID transactions, schema evolution, and time travel to object storage:
  - *Delta Lake*: Databricks-originated; tight Spark integration; widely adopted on AWS/Azure
  - *Apache Iceberg*: Open standard; excellent engine interoperability (Spark, Flink, Trino, Athena); strong schema evolution
  - *Apache Hudi*: Optimized for incremental data updates (upserts) from CDC streams
- **Query Engines**: Query data lake files without moving them — AWS Athena (serverless S3 queries via Presto), Google BigQuery external tables, Trino, Spark SQL. Pay per query rather than provisioning a warehouse
- **Data Lakehouse**: A unified architecture that adds warehouse-like structure (ACID, schema enforcement, performance optimization) to the data lake using open table formats. Eliminates the need for a separate data warehouse for many workloads. Databricks Lakehouse, AWS Lake Formation
- **Partitioning**: Organize files by partition keys (date, region, entity) — queries that filter on partition keys skip entire directories. Critical for query performance and cost (Athena charges per byte scanned)
- **File Formats**: Parquet and ORC are columnar — optimal for analytical queries. Avro is row-oriented — optimal for write-heavy CDC ingestion. JSON/CSV for raw ingestion only; convert to Parquet in the silver layer
- **Data Swamp Risk**: Without governance (catalog, lineage, quality checks, access controls), a data lake becomes an ungoverned data swamp — data exists but nobody knows what it means or whether it's trustworthy

## In Practice
Method data lakes use S3 with Apache Iceberg for the silver and gold layers. Raw data lands in JSON/CSV; Spark jobs transform to Iceberg Parquet in the silver layer. Athena queries the silver and gold layers. AWS Glue Data Catalog registers table metadata. Data quality checks run during silver layer transformation.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Lake**: Organize into raw/silver/gold zones — never modify raw data, it's your source of truth for reprocessing. Use Apache Iceberg or Delta Lake for silver/gold layers: ACID transactions and schema evolution on object storage are non-negotiable at scale. Partition by date and high-cardinality query dimensions — Athena charges per byte scanned and partitioning can cut costs by 90%+. Always convert raw JSON/CSV to Parquet in the first transformation — columnar format dramatically improves query performance. Without a data catalog and lineage, your data lake becomes a data swamp within 6 months. → `engineering-knowledge-repository/data-lake.md`

## Related Entries
- [Data Warehouse](data-warehouse.md) — the data warehouse stores structured analytical data; the lake stores raw and semi-structured data
- [Data Pipelines](data-pipelines.md) — pipelines ingest data into the lake and transform between zones
- [Spark](spark.md) — Spark is the primary processing engine for large-scale data lake transformations
- [Data Quality](data-quality.md) — quality checks at zone boundaries prevent a data swamp
- [Data Catalog](data-catalog.md) — catalogs make lake data discoverable and governable
- [Data Lineage](data-lineage.md) — lineage tracks how data flows between lake zones
- [Data Archiving](data-archiving.md) — the raw lake zone serves as the long-term archive for compliance data

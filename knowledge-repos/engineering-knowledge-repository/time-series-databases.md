---
id: time-series-databases
tags: [database, backend, observability]
surfaces-at: [application-design, functional-design]
related: [metrics-and-alerting, database-indexing, olap-vs-oltp, data-lake, query-optimization, opentelemetry]
complexity: intermediate
---

# Time Series Databases

## What It Is
Databases purpose-built for storing and querying time-indexed data — sequences of values recorded at specific timestamps. Time series data is ubiquitous: server metrics, IoT sensor readings, financial tick data, application performance measurements, energy consumption, and user activity events. General-purpose relational databases can store time series data, but dedicated time series databases (TSDBs) apply optimizations specific to the access pattern: append-only writes, time-range queries, automatic downsampling, and efficient compression of sequential numeric values. These optimizations produce dramatically better write throughput, storage efficiency, and query performance for time series workloads.

## When to Apply
- Storing metrics, monitoring data, or IoT sensor readings at high cardinality or frequency
- When time-range queries ("give me all readings between T1 and T2") dominate your query patterns
- Operational monitoring and alerting pipelines (Prometheus, InfluxDB, Victoria Metrics)
- Financial tick data, trading systems, or any domain where value-over-time is the core query
- When a relational database is struggling with write throughput from high-frequency metric ingestion

## Key Concepts
- **Time Series Characteristics**: Time series data has properties that enable specific optimizations:
  - *Append-only*: New data is always newer than existing data; historical records are rarely updated
  - *Sequential access*: Queries almost always involve a time range (last 5 minutes, last 30 days)
  - *High cardinality*: Many series (one per server, per user, per device) × high frequency = billions of rows
  - *Redundancy*: Values change slowly over time — compression exploits this (delta encoding, run-length encoding)

- **Key TSDBs**:
  - *Prometheus*: The standard for Kubernetes and cloud-native metrics. Pull-based scraping model; PromQL query language; local storage with short retention. Designed for operational metrics, not long-term storage. Pairs with Thanos or Cortex for scalable long-term storage
  - *InfluxDB*: Purpose-built TSDB with line protocol ingestion. Rich query language (Flux). Supports both push and pull models. InfluxDB Cloud provides managed service
  - *TimescaleDB*: PostgreSQL extension that adds time series optimizations (hypertables — automatic partitioning by time, compression, continuous aggregates). Benefit: full SQL with time series performance; operates as standard PostgreSQL for tooling compatibility
  - *Victoria Metrics*: High-performance, cost-efficient Prometheus-compatible TSDB. Better long-term storage than Prometheus; supports Prometheus remote write
  - *Amazon Timestream*: Managed AWS TSDB with automatic tiering to S3 for cold data. Integrates with Grafana and QuickSight
  - *Apache Druid*: Columnar OLAP database optimized for sub-second queries on event streams; often used for high-volume time series analytics

- **Data Model**: Time series data consists of:
  - *Measurement/metric name*: What is being measured ("cpu_usage", "request_latency")
  - *Timestamp*: When the measurement was taken (nanosecond or millisecond precision)
  - *Value*: The numeric measurement
  - *Labels/tags*: Dimensional metadata ("host=web01", "region=us-east-1") — used for filtering and grouping

- **Retention and Downsampling**: High-frequency raw data (per-second metrics) is expensive to retain forever. TSDBs support automatic downsampling — raw data is aggregated into coarser resolution (per-minute, per-hour, per-day) and the raw data is deleted. Prometheus uses recording rules; InfluxDB has downsampling tasks; TimescaleDB uses continuous aggregates

- **Cardinality**: The number of unique time series (metric name × label combinations). High cardinality is the primary scaling challenge in TSDBs. Every unique label combination creates a new series. Avoid using high-cardinality values as labels (user IDs, request IDs) — this creates millions of series and degrades performance

## In Practice
Method infrastructure monitoring uses Prometheus + Grafana for operational metrics. Victoria Metrics provides long-term storage for Prometheus data beyond the 15-day local retention window. Application business metrics are stored in TimescaleDB (on PostgreSQL) when SQL querying and reporting are required. InfluxDB is used in IoT-adjacent engagements where push ingestion and native TSDB semantics are preferred over SQL.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Time Series Databases**: If your write pattern is "append timestamp + value + labels" at high frequency, a general-purpose relational database will become a bottleneck — time-range queries will slow dramatically as the table grows, and storage costs increase linearly without compression. Prometheus is the right choice for Kubernetes metrics; TimescaleDB is the right choice when you need SQL semantics and are already on PostgreSQL. The cardinality trap is the most common TSDB performance problem — don't use user IDs or request IDs as metric labels; they create millions of series that fragment storage and slow queries. → `engineering-knowledge-repository/time-series-databases.md`

## Related Entries
- [Metrics and Alerting](metrics-and-alerting.md) — time series databases are the storage layer for metrics-based alerting systems
- [Database Indexing](database-indexing.md) — TSDBs use specialized index structures (B-trees on time, inverted indexes on labels) optimized for time-range queries
- [OLAP vs. OLTP](olap-vs-oltp.md) — TSDBs occupy a niche between OLTP (high write volume) and OLAP (analytical queries over time ranges)
- [Query Optimization](query-optimization.md) — TSDB query optimization involves different strategies than relational databases (time-range pushdown, metric pre-computation)
- [OpenTelemetry](opentelemetry.md) — OpenTelemetry defines the standards for metric collection that feeds into TSDBs

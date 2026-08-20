---
id: data-pipelines
tags: [pattern, backend, data, distributed-systems]
surfaces-at: [application-design, infrastructure-design]
related: [ml-pipelines, stream-processing, kafka, data-versioning, feature-stores, etl-patterns]
complexity: intermediate
---

# Data Pipelines

## What It Is
Automated workflows that move, transform, and load data from source systems to destination systems reliably and repeatably. Data pipelines are the infrastructure that connects raw data sources (databases, APIs, event streams, files) to the systems that consume data (analytics platforms, ML training, data warehouses, operational stores). Without reliable pipelines, ML models train on stale or incorrect data, analytics are delayed, and data quality issues compound.

## When to Apply
- Any system that ingests data from external sources for processing, analytics, or ML
- Moving data between operational databases and analytics/ML stores
- ETL/ELT workflows that transform raw data into structured, usable form
- Real-time or near-real-time data feeds for operational systems

## Key Concepts
- **ETL (Extract, Transform, Load)**: Extract data from sources, transform it (clean, join, aggregate), load to destination. Traditional batch approach
- **ELT (Extract, Load, Transform)**: Load raw data first, transform inside the destination (data warehouse). Preferred for cloud data warehouses — transformation happens in Snowflake/BigQuery/Redshift using SQL
- **Orchestration**: Tools that schedule, monitor, and manage pipeline execution — Apache Airflow, Prefect, Dagster. Define pipelines as DAGs (directed acyclic graphs) of tasks
- **Idempotency**: Pipeline runs should produce the same result whether run once or many times. Critical for reruns after failure — idempotent pipelines are safe to retry
- **Incremental vs. Full Load**: Incremental loads process only new/changed data since the last run (using watermarks, change data capture). Full loads reload all data — simpler but expensive at scale
- **Change Data Capture (CDC)**: Capture database changes in real time from the database's transaction log — Debezium with Kafka is the standard approach. Enables near-real-time data movement without polling
- **Data Quality Checks**: Validate data at pipeline checkpoints — row counts, null rates, value distributions, schema validation. Gate pipeline progression on quality thresholds. Great Expectations and dbt tests implement this
- **Lineage**: Track where data came from and what transformations were applied — essential for debugging data quality issues and regulatory compliance. OpenLineage, dbt lineage, Marquez

## In Practice
Method data pipelines use Apache Airflow for batch ETL orchestration. CDC pipelines use Debezium + Kafka for near-real-time database-to-data-warehouse sync. dbt handles SQL transformations in the data warehouse (ELT pattern). Data quality checks are embedded as Airflow tasks that gate downstream pipeline stages.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Pipelines**: Design pipelines to be idempotent — reruns after failure must be safe. Use ELT with dbt for data warehouse workloads: raw data lands in the warehouse first, transformations happen in SQL where they're auditable and version-controlled. Embed data quality checks as pipeline gates — don't pass bad data downstream silently. Use CDC (Debezium + Kafka) for near-real-time data movement instead of polling databases. Track lineage from the start — tracing a data quality issue through 10 pipeline stages without lineage is painful. → `engineering-knowledge-repository/data-pipelines.md`

## Related Entries
- [ML Pipelines](ml-pipelines.md) — ML pipelines extend data pipelines with training, evaluation, and model deployment stages
- [Stream Processing](stream-processing.md) — stream processing is the real-time computation layer within data pipelines
- [Kafka](kafka.md) — Kafka is the event streaming backbone for real-time data pipeline ingestion
- [Data Versioning](data-versioning.md) — data pipeline outputs must be versioned for ML reproducibility
- [Feature Stores](feature-stores.md) — feature stores are a destination for pipeline-computed ML features
- [ETL Patterns](etl-patterns.md) — ETL-specific patterns and anti-patterns within data pipeline design

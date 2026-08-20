---
id: data-quality
tags: [methodology, data, backend]
surfaces-at: [functional-design, application-design]
related: [data-pipelines, data-warehouse, data-lake, data-contracts, etl-patterns, data-lineage]
complexity: intermediate
---

# Data Quality

## What It Is
The practice of ensuring data is accurate, complete, consistent, timely, and fit for its intended use — and the tooling and processes that enforce these properties systematically. Poor data quality is one of the most expensive problems in data engineering: ML models trained on bad data produce wrong predictions, dashboards built on incorrect data mislead decisions, and bugs caused by unexpected data formats are difficult to diagnose. Data quality must be built into pipelines as executable, monitored checks — not assumed.

## When to Apply
- At every stage boundary in a data pipeline (ingestion, transformation, serving)
- Before data lands in a data warehouse or is used for ML training
- When data is shared across teams (producer-consumer data contracts)
- Any time a data issue could silently affect downstream decisions or models

## Key Concepts
- **Dimensions of Data Quality**:
  - *Completeness*: Required fields are present; no unexpected nulls
  - *Accuracy*: Values are correct and within valid ranges
  - *Consistency*: Data conforms to expected formats, types, and business rules
  - *Timeliness*: Data arrives when expected; freshness SLAs are met
  - *Uniqueness*: No unexpected duplicates on key columns
- **Great Expectations**: The leading open-source data quality framework. Define "expectations" (assertions) about data — column types, value ranges, null rates, referential integrity. Run expectations as pipeline tests; generate data quality reports
- **dbt Tests**: Built-in data quality tests for dbt models — `not_null`, `unique`, `accepted_values`, `relationships` (referential integrity). Custom tests via dbt macros. Run in CI and as part of every pipeline run. The standard for data warehouse quality
- **Data Profiling**: Statistical analysis of a dataset — value distributions, null rates, cardinality, min/max, outlier detection. Run profiling before building pipelines on a new data source; surfaces quality issues before they propagate
- **Pipeline Quality Gates**: Quality checks that block pipeline progression on failure — don't pass bad data to the next stage. Fail loudly and alert; never silently pass bad data downstream
- **Data SLAs**: Define freshness SLAs per dataset — "orders table updated within 30 minutes of event." Monitor and alert on SLA violations. Consumers should know when data is stale
- **Anomaly Detection on Data**: Detect unexpected drops in row counts, sudden null rate increases, or distribution shifts in key columns. These are leading indicators of upstream data problems
- **Schema Validation**: Validate that incoming data conforms to the expected schema before processing. Schema Registry (Kafka), Pydantic, JSON Schema — catch schema changes at the boundary before they break pipelines
- **Root Cause and Lineage**: When a quality check fails, lineage (which source systems and transformations produced this data) is essential for diagnosis. Quality and lineage are inseparable

## In Practice
Method embeds dbt tests in all warehouse transformation pipelines. Great Expectations runs at ingestion for raw source data. Pipeline DAGs gate on quality check tasks — downstream tasks don't run if quality checks fail. Freshness SLAs are monitored via Airflow sensors. Data quality failures alert to the team Slack channel.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Quality**: Embed quality checks as pipeline gates, not manual audits — bad data must fail loudly before it reaches consumers. Use dbt tests for warehouse data; Great Expectations for raw ingestion. Always check completeness (nulls on required fields), uniqueness (duplicates on key columns), and freshness (data arrived on time). Monitor row count trends and null rate trends as leading indicators — sudden changes signal upstream problems before downstream failures occur. Quality without lineage is incomplete — when a check fails, you need to know where the bad data came from. → `engineering-knowledge-repository/data-quality.md`

## Related Entries
- [Data Pipelines](data-pipelines.md) — quality gates are embedded as pipeline stages
- [Data Warehouse](data-warehouse.md) — dbt tests enforce quality on warehouse transformation outputs
- [Data Lake](data-lake.md) — quality checks at zone boundaries prevent the data lake from becoming a data swamp
- [Data Contracts](data-contracts.md) — data contracts formalize quality expectations between producers and consumers
- [ETL Patterns](etl-patterns.md) — quality gates are a required pattern in ETL pipeline design
- [Data Lineage](data-lineage.md) — lineage enables root cause analysis when quality checks fail

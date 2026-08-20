---
id: etl-patterns
tags: [pattern, backend, data]
surfaces-at: [functional-design, application-design]
related: [data-pipelines, batch-processing, data-versioning, idempotency]
complexity: intermediate
---

# ETL Patterns

## What It Is
Design patterns and best practices for Extract, Transform, Load data workflows — the structured approach to reliably moving and transforming data between systems. ETL patterns address recurring challenges in data pipeline design: handling failures gracefully, ensuring data quality, managing incremental updates, and making pipelines observable and maintainable. Well-designed ETL pipelines are idempotent, observable, and testable.

## When to Apply
- Designing data ingestion pipelines from operational databases to analytics stores
- Building data warehouse loading workflows
- Any workflow that transforms raw source data into a structured destination format

## Key Concepts
- **Incremental Load Pattern**: Process only new or changed records since the last successful run using a high-watermark (max timestamp or ID). Avoids full reloads and scales with data volume. Requires a reliable change indicator on source data
- **Full Refresh Pattern**: Truncate and reload the destination table completely. Simple and correct — no watermark tracking required. Only feasible for small-to-medium tables
- **Idempotent Upsert**: Write data in an upsert pattern (insert-or-update by primary key) — safe to run multiple times, handles late-arriving records, prevents duplicate rows. The default for dimension tables
- **Staging Pattern**: Land raw extracted data in a staging area first; transform from staging to final destination. Decouples extraction from transformation — extraction failures don't corrupt final tables
- **Partitioned Overwrite**: For fact tables, overwrite one partition (e.g., one day) at a time. Idempotent — re-running replaces the partition rather than appending duplicates. Standard pattern for dbt incremental models
- **Checkpointing / Offset Tracking**: Record the last successfully processed position (timestamp, offset, ID) — enables resumption from the failure point rather than full restart
- **Data Quality Gates**: Assert row counts, null rates, and value ranges before committing transformed data to the destination. Fail the pipeline and alert rather than propagating bad data silently
- **Schema Evolution**: Source schemas change over time — handle gracefully with additive-only changes where possible; version the pipeline for breaking changes

## In Practice
Method ETL pipelines use the staging → transform → upsert pattern. dbt incremental models use partitioned overwrite for fact tables and upsert for dimension tables. Data quality tests run after each transformation step via dbt tests and Great Expectations. Watermarks are stored in a pipeline state table.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — ETL Patterns**: Use staging tables — never transform directly from source to final destination in a single step. Idempotent upserts beat append-only inserts for anything that might rerun. Track watermarks explicitly in a state table; don't infer from destination data. Run data quality assertions before writing to final tables — failing loudly beats silently writing garbage. For large fact tables, partitioned overwrite (replace one day at a time) is the idempotent write pattern. → `engineering-knowledge-repository/etl-patterns.md`

## Related Entries
- [Data Pipelines](data-pipelines.md) — ETL patterns are applied within data pipeline design
- [Batch Processing](batch-processing.md) — ETL is typically implemented as batch processing
- [Data Versioning](data-versioning.md) — version pipeline inputs and transformation logic for reproducibility
- [Idempotency](idempotency.md) — idempotency is the foundational property all ETL patterns should achieve

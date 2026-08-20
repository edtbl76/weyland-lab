---
id: data-archiving
tags: [pattern, cost, database, data]
surfaces-at: [application-design, infrastructure-design]
related: [database-cost-optimization, data-versioning, data-pipelines, finops]
complexity: intermediate
---

# Data Archiving

## What It Is
The process of moving data that is no longer actively needed for operational queries from expensive primary storage (databases, hot object storage) to cheaper, slower archival storage (cold object storage, data lakes, tape). Archiving reduces primary database size, improves query performance, lowers storage costs, and helps meet data retention compliance requirements. The key design challenge is defining what "inactive" means and ensuring archived data remains accessible when needed.

## When to Apply
- Database tables that grow unboundedly over time (events, logs, audit trails, transactions)
- Data with clear temporal access patterns — recent data is hot, old data is cold
- Compliance requirements that mandate long-term retention but allow cold storage
- When storage costs are growing faster than active data volume

## Key Concepts
- **Hot / Warm / Cold Tiers**:
  - *Hot*: Primary database — fast queries, expensive. Active data accessed regularly
  - *Warm*: Compressed, queryable storage (S3 + Athena, BigQuery, Redshift Spectrum) — slower queries, much cheaper. Recent history
  - *Cold*: Long-term archive (S3 Glacier, GCS Archive) — infrequent access, cheapest. Compliance retention
- **Archiving Strategy**: Define the retention period for hot storage per table type. Common patterns: keep 90 days in the database, 1 year in warm storage, 7 years in cold archive. Align with legal and compliance retention requirements
- **Partitioned Archiving**: Archive by time partition — move all records older than a threshold in batches. Avoid row-by-row deletion in large tables; partition pruning and batch deletes are more efficient
- **Soft Delete vs. Physical Archive**: Soft delete (mark as deleted) keeps records in the primary database — does not reduce storage. Physical archiving moves data out of the primary. Soft delete is a logical operation; archiving is a cost and performance operation
- **Query Access to Archived Data**: Ensure archived data is queryable for compliance, support, and analytics. S3 + Athena, BigQuery external tables, or Redshift Spectrum enable SQL queries on archived S3 data at low cost per query
- **Referential Integrity**: Archiving records that are referenced by other tables requires careful handling — foreign key constraints must be relaxed or dependent records archived together
- **Compliance and GDPR**: Data archiving and deletion must account for right-to-erasure requirements. Archived data must be deletable. Document where data lives across all tiers

## In Practice
Method archives database tables older than 90 days to S3 in Parquet format. Athena queries archived data for compliance and analytics. Archiving jobs run nightly as Airflow tasks. Parquet files are partitioned by date for efficient querying. S3 lifecycle policies transition data to Glacier after 1 year.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Archiving**: Define data retention tiers at schema design time, not after the table is already 500GB. Archive by time partition in batches — not row-by-row. Move archived data to S3 in Parquet format and query with Athena — you get SQL access at a fraction of database storage cost. Set S3 lifecycle policies to automatically transition to Glacier for long-term compliance retention. Ensure archived data is deletable for GDPR right-to-erasure compliance. The combination of database (90 days hot) + S3/Athena (1 year warm) + Glacier (7 years cold) covers most compliance requirements at minimum cost. → `engineering-knowledge-repository/data-archiving.md`

## Related Entries
- [Database Cost Optimization](database-cost-optimization.md) — data archiving is the primary lever for reducing database storage costs
- [Data Versioning](data-versioning.md) — archived datasets should be versioned for reproducibility and audit
- [Data Pipelines](data-pipelines.md) — archiving jobs are data pipeline tasks that extract and load data to archival storage
- [FinOps](finops.md) — data archiving is a cost optimization tracked within the FinOps storage cost framework

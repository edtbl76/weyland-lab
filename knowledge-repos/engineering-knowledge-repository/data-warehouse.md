---
id: data-warehouse
tags: [pattern, data, backend, cloud]
surfaces-at: [application-design, infrastructure-design]
related: [data-lake, olap-vs-oltp, data-pipelines, etl-patterns, data-quality, data-catalog, data-lineage]
complexity: intermediate
---

# Data Warehouse

## What It Is
A centralized analytical database optimized for querying and reporting across large volumes of historical data from multiple source systems. Unlike OLTP databases optimized for transactional workloads (fast writes, row-level access), data warehouses use columnar storage, massively parallel processing, and denormalized schemas to execute complex analytical queries efficiently. Modern cloud data warehouses (Snowflake, BigQuery, Redshift) are fully managed, scale compute and storage independently, and support the ELT pattern where raw data lands first and transformations happen inside the warehouse using SQL.

## When to Apply
- Centralizing analytical data from multiple operational systems for reporting and BI
- Running complex analytical queries that would overwhelm OLTP databases
- Building a single source of truth for business metrics
- Supporting data science and ML feature engineering on historical data

## Key Concepts
- **Columnar Storage**: Data is stored column-by-column rather than row-by-row. Analytical queries that aggregate a few columns across millions of rows read only the relevant columns — dramatically reduces I/O. Contrast with row-oriented OLTP databases that read entire rows
- **MPP (Massively Parallel Processing)**: Queries are distributed across many compute nodes automatically. More compute nodes = faster queries on large datasets. Cloud warehouses scale compute independently of storage
- **ELT vs. ETL**: Modern warehouses favor ELT — load raw data first, transform inside the warehouse using SQL. Transformations are version-controlled, auditable, and rerunnable. dbt is the standard tool for ELT transformations
- **Schemas — Star and Snowflake**: Dimensional modeling organizes data into fact tables (measures/events) and dimension tables (descriptive attributes). Star schema: fact table with direct dimension joins. Snowflake schema: normalized dimensions. Star schema is preferred for query performance
- **dbt (data build tool)**: SQL-based transformation framework that runs inside the warehouse. Models are SELECT statements; dbt handles materialization, dependency ordering, testing, and documentation. The standard for ELT transformations
- **Snowflake**: Separated compute and storage; multi-cluster warehouses; time travel (query historical data); zero-copy cloning. Dominant in enterprise data warehousing
- **BigQuery**: Google's serverless warehouse — no infrastructure management; pricing per query (bytes scanned) or flat-rate. Excellent for Google ecosystem and ML integration (BigQuery ML)
- **Redshift**: AWS's warehouse — tightly integrated with the AWS ecosystem; Redshift Spectrum queries S3 directly. Better for workloads already on AWS
- **Separation of Compute and Storage**: Modern warehouses store data in cloud object storage (S3, GCS) and attach compute clusters on demand. Scale compute for query performance without paying for idle compute

## In Practice
Method uses Snowflake as the default data warehouse. dbt handles all ELT transformations. Raw source data lands in a staging layer; transformed business models are in a presentation layer. Airflow orchestrates the ingestion pipeline; dbt runs transformations. Query results feed BI tools (Tableau, Looker) and ML feature pipelines.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Warehouse**: Use ELT not ETL — load raw data into the warehouse first and transform with dbt. Raw data is preserved and transformations are rerunnable. Dimensional modeling (star schema) is the right structure for analytical queries — fact tables with dimension joins, not normalized OLTP schemas. Separate staging (raw), intermediate (cleaned), and presentation (business) layers in your dbt project. Snowflake and BigQuery both separate compute from storage — scale compute for performance, scale storage independently. Size warehouses for query SLAs, not data volume. → `engineering-knowledge-repository/data-warehouse.md`

## Related Entries
- [Data Lake](data-lake.md) — the data lake stores raw unstructured/semi-structured data; the warehouse stores structured analytical data
- [OLAP vs. OLTP](olap-vs-oltp.md) — data warehouses implement OLAP workloads; understanding the distinction drives design decisions
- [Data Pipelines](data-pipelines.md) — pipelines ingest source data into the warehouse staging layer
- [ETL Patterns](etl-patterns.md) — ELT patterns within the warehouse replace traditional ETL transformations
- [Data Quality](data-quality.md) — dbt tests and data quality checks are embedded in warehouse transformation pipelines
- [Data Catalog](data-catalog.md) — data catalogs document and make warehouse tables discoverable
- [Data Lineage](data-lineage.md) — dbt lineage tracks how warehouse models are derived from source data

---
id: olap-vs-oltp
tags: [reference, data, database, backend]
surfaces-at: [application-design, requirements-analysis]
related: [data-warehouse, database-transactions, database-indexing, polyglot-persistence, read-replicas]
complexity: beginner
---

# OLAP vs. OLTP

## What It Is
Two fundamental database workload categories with different characteristics, optimization goals, and tooling. OLTP (Online Transaction Processing) handles the high-volume, low-latency reads and writes of operational systems. OLAP (Online Analytical Processing) handles complex queries over large volumes of historical data for analytics and reporting. Using the wrong database type for a workload — running analytics on an OLTP database or transactional writes against an OLAP system — leads to poor performance and high cost. Understanding this distinction drives correct data architecture decisions.

## When to Apply
- Choosing a database for a new system or feature
- Deciding whether to build a separate analytical data store
- Diagnosing performance problems caused by analytical queries hitting operational databases

## Key Concepts

**OLTP Characteristics**:
- High volume of short, simple transactions (INSERT, UPDATE, DELETE, point lookups)
- Optimized for row-level access — fetch one or few rows per query
- Row-oriented storage — reading a full row is fast
- Heavily normalized schema — minimize data duplication, maintain integrity
- Optimized for write performance and concurrency
- Databases: PostgreSQL, MySQL, SQL Server, Oracle, DynamoDB

**OLAP Characteristics**:
- Low volume of complex, long-running queries (aggregations, joins across large datasets)
- Optimized for column-level access — scan millions of rows but only a few columns
- Columnar storage — reading a single column across all rows is fast; writing is slower
- Denormalized schema (star/snowflake) — minimize joins for query performance
- Optimized for read throughput and query speed
- Databases: Snowflake, BigQuery, Redshift, ClickHouse, DuckDB

**The Problem with Mixing Workloads**:
- Running analytical queries on an OLTP database: full table scans compete with transactional operations, degrade response times, and hold locks that block writes
- Running transactional writes against a data warehouse: columnar storage is inefficient for row-level writes; concurrent write performance is poor

**Common Patterns**:
- Separate OLTP (operational DB) from OLAP (data warehouse) — replicate data via ETL/CDC
- Read replicas for moderate analytical workloads before graduating to a full warehouse
- HTAP (Hybrid Transactional/Analytical Processing): newer databases (TiDB, SingleStore) claim to handle both — suitable for moderate workloads where operational latency requirements are relaxed

**OLAP for Operational Analytics**:
- Some products need near-real-time analytics (dashboards updated every few minutes). Options: materialized views on OLTP, dedicated OLAP with short refresh intervals (ClickHouse), or streaming aggregation into an OLAP store

## In Practice
Method uses PostgreSQL for all OLTP workloads and Snowflake for analytical workloads. Data is replicated from Postgres to Snowflake via CDC (Debezium + Kafka) with a 5-15 minute lag. Analytical queries that can tolerate that lag hit Snowflake; latency-sensitive operational queries hit Postgres read replicas.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — OLAP vs. OLTP**: Never run heavy analytical queries against your operational database — they will degrade response times for users. Route reporting, aggregations, and BI queries to a dedicated analytical store. Use read replicas as a stepping stone; graduate to a data warehouse when query complexity and data volume justify it. OLAP databases (Snowflake, BigQuery) are dramatically cheaper and faster for analytical workloads than running the same queries on PostgreSQL. Columnar storage is the reason — scanning 3 columns of 100M rows reads 3% of the data that row-oriented storage would. → `engineering-knowledge-repository/olap-vs-oltp.md`

## Related Entries
- [Data Warehouse](data-warehouse.md) — data warehouses are the OLAP layer in a modern data architecture
- [Database Transactions](database-transactions.md) — ACID transactions are the defining feature of OLTP databases
- [Database Indexing](database-indexing.md) — indexing strategies differ significantly between OLTP and OLAP workloads
- [Polyglot Persistence](polyglot-persistence.md) — using different databases for different workloads is the polyglot persistence pattern
- [Read Replicas](read-replicas.md) — read replicas are a stepping stone from OLTP to dedicated OLAP for moderate analytical workloads

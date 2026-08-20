---
id: materialized-views
tags: [pattern, database, data, performance, backend]
surfaces-at: [functional-design, application-design]
related: [database-indexing, olap-vs-oltp, cqrs, data-warehouse, read-replicas, query-optimization]
complexity: intermediate
---

# Materialized Views

## What It Is
A database object that stores the precomputed result of a query as a physical table. Unlike a regular view (which re-executes the query on every access), a materialized view computes the result once and stores it — subsequent reads are fast table scans or index lookups on the precomputed data. Materialized views trade storage and refresh cost for dramatically faster reads on expensive aggregations, joins, and computations. They are widely used in both OLTP databases (PostgreSQL, SQL Server) and OLAP systems (Snowflake, BigQuery, Redshift).

## When to Apply
- Frequently queried aggregations or joins that are expensive to compute on demand
- Dashboard queries that run against the same data repeatedly
- CQRS read models — precomputed views of write-model data optimized for specific read patterns
- Caching complex query results within the database layer

## Key Concepts
- **Refresh Strategies**:
  - *Full refresh*: Recompute the entire result set. Simple; expensive for large datasets; produces consistent results
  - *Incremental refresh*: Append or update only changed rows. Faster and cheaper; requires change detection logic. Snowflake Dynamic Tables and dbt incremental models implement this
  - *On-demand refresh*: Triggered manually or by a schedule. PostgreSQL `REFRESH MATERIALIZED VIEW`
  - *Automatic/real-time refresh*: Some databases (Snowflake Dynamic Tables, BigQuery materialized views) automatically refresh when underlying data changes
- **Staleness**: Materialized views are only as fresh as their last refresh. Define acceptable staleness based on the use case — dashboard data can often tolerate minutes; operational data may require seconds
- **PostgreSQL Materialized Views**: `CREATE MATERIALIZED VIEW name AS SELECT ...`. Refresh with `REFRESH MATERIALIZED VIEW CONCURRENTLY` (non-blocking). Can be indexed like regular tables. Manual refresh required unless scheduled via pg_cron or a pipeline
- **Snowflake Dynamic Tables**: Declarative materialized views that automatically refresh when source data changes. Define the refresh lag (target latency). Replaces manual scheduling of dbt models for near-real-time use cases
- **dbt Models as Materialized Views**: dbt `materialized = 'table'` or `'incremental'` configurations create materialized query results in the data warehouse. The standard way to build and maintain materialized views at the warehouse layer
- **Index on Materialized Views**: In PostgreSQL, indexes on materialized views work like indexes on tables — add indexes for the query patterns that will access the view
- **CQRS Read Models**: In CQRS architectures, materialized views implement the read model — a denormalized, precomputed representation of the write model optimized for specific query patterns. Updated asynchronously as events arrive

## In Practice
Method uses PostgreSQL materialized views for dashboard queries requiring sub-second response times on large aggregations. Snowflake Dynamic Tables serve near-real-time analytical use cases. dbt incremental models implement data warehouse materializations. CQRS read models are implemented as PostgreSQL materialized views refreshed via event-driven triggers.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Materialized Views**: Materialized views are the right tool when the same expensive query is executed repeatedly — precompute once, serve many times. In PostgreSQL, use `REFRESH MATERIALIZED VIEW CONCURRENTLY` to avoid locking readers during refresh. Index materialized views for the access patterns of their consumers — they behave like regular tables. Define acceptable staleness upfront and choose refresh strategy accordingly. For data warehouses, dbt incremental models and Snowflake Dynamic Tables are the idiomatic materialization approach. Don't use materialized views as a substitute for fixing a poorly written query — profile first. → `engineering-knowledge-repository/materialized-views.md`

## Related Entries
- [Database Indexing](database-indexing.md) — materialized views can be indexed like regular tables for fast access
- [OLAP vs. OLTP](olap-vs-oltp.md) — materialized views bridge OLTP data and OLAP query patterns
- [CQRS](cqrs.md) — materialized views implement the read model in CQRS architectures
- [Data Warehouse](data-warehouse.md) — dbt models are the warehouse-native form of materialized views
- [Read Replicas](read-replicas.md) — materialized views and read replicas both serve read-heavy workloads; views are for specific queries, replicas for general read offloading
- [Query Optimization](query-optimization.md) — materialized views are a query optimization strategy for repeated expensive computations

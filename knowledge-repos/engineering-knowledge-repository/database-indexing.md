---
id: database-indexing
tags: [pattern, performance, database]
surfaces-at: [functional-design, nfr-requirements, code-generation]
related: [query-optimization, n-plus-one-query, caching-strategies]
complexity: intermediate
---

# Database Indexing

## What It Is
A database data structure that improves query performance by creating a lookup path to rows matching specific column values — without scanning the entire table. An index trades write overhead and storage for dramatically faster reads. Without indexes on frequently-queried columns, the database performs a full table scan for every query — O(n) per query instead of O(log n) with a B-tree index.

## When to Apply
- Columns used in WHERE clauses of frequent queries
- Columns used in JOIN conditions
- Columns used in ORDER BY or GROUP BY when sorting matters for performance
- Foreign key columns (automatically created in some databases, must be explicit in PostgreSQL)
- Unique constraints — always backed by a unique index

## When Not to Apply
- Every column — indexes slow writes and consume storage. Only index what's needed.
- Low-cardinality columns (boolean, status with 3 values) — the database often prefers a table scan over a low-cardinality index
- Very small tables — a table scan of 100 rows is trivially fast regardless of indexing
- Write-heavy tables where index maintenance overhead outweighs query benefits

## Key Concepts
- **B-Tree Index**: The standard, default index type — supports equality, range, sorting. Works for most use cases.
- **Hash Index**: Only supports equality checks — faster for exact lookups but useless for ranges. Less common.
- **Composite Index**: An index on multiple columns — column order matters. A composite index on (A, B) helps queries filtering on A alone or A+B together, but not B alone.
- **Covering Index**: An index that includes all columns needed for a query — the database can answer the query entirely from the index without touching the table ("index-only scan")
- **Partial Index**: An index on a subset of rows matching a condition — smaller, faster for specific query patterns
- **EXPLAIN ANALYZE**: The command to inspect query execution plans — reveals whether indexes are being used and where bottlenecks are
- **Index Bloat**: Indexes on tables with frequent updates/deletes grow bloated — periodic `VACUUM` / `REINDEX` maintains health in PostgreSQL

## In Practice
Index strategy is reviewed in Method engagements during functional design (what queries will be common?) and validated in load testing (EXPLAIN ANALYZE on slow queries). Start with indexes on all foreign keys and WHERE clause columns for the highest-traffic queries. Add composite indexes when queries consistently filter on multiple columns together.

## Engineering Knowledge
💡 **Engineering Knowledge — Database Indexing**: Without an index, every query scans the whole table. Index your WHERE, JOIN, and ORDER BY columns — but not every column. Column order in composite indexes matters: (user_id, created_at) helps queries filtering by user_id alone or user_id+created_at, but not created_at alone. Use `EXPLAIN ANALYZE` to verify indexes are being used. Index writes slow down insert/update performance — only index what's actually queried. → `engineering-knowledge-repository/performance/database-indexing.md`

## Related Entries
- [Query Optimization](query-optimization.md) — indexing is the most impactful single query optimization
- [N+1 Query Problem](n-plus-one-query.md) — indexes help N+1 queries, but don't fix the structural problem

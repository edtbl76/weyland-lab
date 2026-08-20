---
id: query-optimization
tags: [pattern, performance, database]
surfaces-at: [nfr-requirements, functional-design, code-generation]
related: [database-indexing, n-plus-one-query, caching-strategies, connection-pooling]
complexity: intermediate
---

# Query Optimization

## What It Is
The process of improving database query performance through schema design, query rewriting, indexing, and execution plan analysis. Slow queries are often the root cause of poor application performance — a single unoptimized query in a hot code path can degrade an entire service under load.

## When to Apply
- When load testing identifies slow API response times
- When database slow query logs reveal queries taking over 100ms
- During code review for queries in high-traffic code paths
- Before launching features with complex reporting or search queries

## Key Concepts
- **EXPLAIN / EXPLAIN ANALYZE**: The primary diagnostic tool — shows the query execution plan. Look for Sequential Scans on large tables, high row estimates, and expensive sort operations.
- **Sequential Scan vs. Index Scan**: A Seq Scan reads every row; an Index Scan follows the index to matching rows. For large tables, Seq Scans are usually the problem.
- **Query Plan Optimization**:
  - Add indexes for missing index scans
  - Rewrite queries to avoid full table scans
  - Avoid `SELECT *` — fetch only needed columns
  - Use EXISTS instead of COUNT for existence checks
  - Avoid functions on indexed columns in WHERE clauses (`WHERE LOWER(email) = ...` prevents index use)
- **JOIN Order**: The query planner chooses join order; hints or query rewrites can help when the planner makes suboptimal choices on complex joins
- **Pagination**: `OFFSET`-based pagination becomes slow at large offsets — use cursor-based (keyset) pagination for deep pages
- **Materialized Views**: For expensive aggregation queries run frequently — compute once, store the result
- **Parameterized Queries**: Beyond security (SQL injection prevention), parameterized queries enable execution plan caching — the plan is compiled once and reused

## In Practice
Query optimization is a standard Method recommendation during performance investigation. The workflow: identify slow queries via slow query log → run EXPLAIN ANALYZE → identify the bottleneck (missing index, full scan, bad join) → apply targeted fix → verify improvement. Don't optimize speculatively — profile first.

## Engineering Knowledge
💡 **Engineering Knowledge — Query Optimization**: Slow queries are the most common application performance problem. Diagnose with `EXPLAIN ANALYZE` — look for Seq Scans on large tables. Add the right index: on the WHERE column, in the right order for composite indexes, as a covering index if the query reads only indexed columns. Avoid functions on indexed columns in WHERE clauses. Use cursor-based pagination instead of OFFSET for large datasets. Profile first, optimize second — don't guess. → `engineering-knowledge-repository/performance/query-optimization.md`

## Related Entries
- [Database Indexing](database-indexing.md) — the primary tool for query optimization
- [N+1 Query Problem](n-plus-one-query.md) — a specific query pattern that query optimization must address
- [Caching Strategies](caching-strategies.md) — when optimization isn't enough, caching the query result is the next lever

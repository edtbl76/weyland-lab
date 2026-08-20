---
id: n-plus-one-query
tags: [anti-pattern, performance, database, backend]
surfaces-at: [functional-design, code-generation, nfr-requirements]
related: [caching-strategies, query-optimization, database-indexing]
complexity: foundational
---

# N+1 Query Problem

## What It Is
A performance anti-pattern where code executes 1 query to fetch N parent records, then executes N additional queries to fetch associated data for each parent — resulting in N+1 total database queries instead of 1 or 2. The classic example: fetch 100 orders (1 query), then loop through orders and fetch the customer for each (100 queries) = 101 queries total. N+1 queries are a common cause of unexpectedly slow API responses and database overload.

## When to Apply (How to Detect and Fix)
- Any ORM-based code with nested object access in loops
- Slow API responses that are suspiciously proportional to the number of records returned
- Database performance monitoring showing many similar queries executing in rapid sequence
- Code review of data access patterns — look for loops with database calls inside

## Key Concepts
- **1 Query**: Load all parent records from the database
- **N Queries**: One query per parent record to load a related association — the problem
- **Eager Loading**: The fix — load associations upfront using JOIN or IN queries rather than lazy per-record loads. ORM support: `include` (ActiveRecord), `JOIN FETCH` (JPA), `.Include()` (EF Core), `prefetch_related` (Django ORM).
- **Batch Loading (DataLoader Pattern)**: For cases where eager loading isn't practical — collect all IDs needed, fetch in one batched query. Facebook's DataLoader implements this for GraphQL resolvers.
- **ORM Lazy Loading**: The default behavior in many ORMs — associations are loaded only when accessed. Convenient for development, catastrophic for production performance at scale.
- **Query Logging**: Enable query logging in development and staging to detect N+1 patterns before production — look for repeated similar queries
- **EXPLAIN**: Analyze query execution plans to identify missing indexes that make N+1 queries even slower

## In Practice
N+1 is one of the most common performance bugs Method finds in inherited codebases. The diagnostic: enable ORM query logging in staging and look for repeated identical queries with slightly different parameters. The fix is almost always eager loading or batch loading. Test performance with representative data volumes — N+1 problems are invisible with small test datasets.

## Engineering Knowledge
💡 **Engineering Knowledge — N+1 Query Problem**: Loading 100 orders and then fetching each customer one at a time is 101 queries, not 2. ORM lazy loading makes this easy to create accidentally. Fix: eager load associations with JOIN/INCLUDE, or batch with DataLoader. Enable ORM query logging in staging and look for repeated queries in loops — this is the fastest way to find N+1. Test with realistic data volumes: N+1 is invisible with 5 test records. → `engineering-knowledge-repository/performance/n-plus-one-query.md`

## Related Entries
- [Caching Strategies](caching-strategies.md) — caching batch-loaded data can further reduce database load
- [Query Optimization](query-optimization.md) — N+1 is a specific instance of the broader query optimization problem
- [Database Indexing](database-indexing.md) — indexes help, but they don't fix the N+1 structural problem

---
id: caching-strategies
tags: [pattern, performance, backend, database]
surfaces-at: [nfr-requirements, nfr-design, functional-design]
related: [horizontal-vs-vertical-scaling, n-plus-one-query, connection-pooling, polyglot-persistence]
complexity: intermediate
---

# Caching Strategies

## What It Is
Techniques for storing computed or retrieved data in a faster storage layer (memory) so subsequent requests can be served without re-computing or re-fetching from the slower source. Caching is one of the highest-leverage performance improvements available — a cache hit can be 100-1000x faster than the equivalent database query. But caching introduces consistency challenges: cached data can be stale.

## When to Apply
- Read-heavy workloads where the same data is requested repeatedly
- Expensive computations or queries that produce results used by many requests
- External API calls where rate limits or latency make repeated calls expensive
- Session data, user preferences, reference data that changes infrequently

## When Not to Apply
- Highly volatile data where stale reads are unacceptable
- Data that is different per user with high cardinality — caching effectiveness is low when cache keys are unique per request
- Before profiling — cache what's slow, not everything speculatively

## Key Concepts
- **Cache-Aside (Lazy Loading)**: Application checks the cache; on miss, loads from source and populates the cache. Most common pattern. App has full control.
- **Read-Through**: Cache handles the miss — transparently fetches from source on miss. Simpler application code; requires a cache that supports read-through.
- **Write-Through**: Every write goes to both cache and source simultaneously. Cache is always current; write latency increases.
- **Write-Behind (Write-Back)**: Writes go to cache first, asynchronously persisted to source. Low write latency; risk of data loss if cache fails before persistence.
- **Cache-Invalidation**: The hard problem — when source data changes, how are cached copies invalidated? Strategies: TTL (time-to-live), event-driven invalidation, cache tags.
- **TTL (Time-to-Live)**: The expiry time for a cache entry — balances freshness against cache efficiency
- **Cache Stampede**: When many requests miss the cache simultaneously (e.g., after TTL expiry) and all try to repopulate — use locking or background refresh to prevent
- **Redis / Memcached**: The standard caching infrastructure — Redis is preferred (supports data structures, persistence, pub/sub)

## In Practice
Cache-aside with Redis is Method's standard caching pattern for web services. Cache TTL is a business decision — how stale is acceptable? Reference data (product catalog, configuration) tolerates longer TTLs; user-specific data requires shorter TTLs or event-driven invalidation. Monitor cache hit rate — a low hit rate means the cache isn't providing value.

## Engineering Knowledge
💡 **Engineering Knowledge — Caching Strategies**: Cache what's slow and requested often. Cache-aside with Redis is the standard: check cache, miss → load from DB → populate cache. Choose TTL based on how stale the data can be. The hard problem is invalidation — either accept staleness via TTL or implement event-driven invalidation for data that changes frequently. Monitor hit rate: below 80% means you're caching the wrong things. Cache stampede prevention: use locking on cache misses. → `engineering-knowledge-repository/performance/caching-strategies.md`

## Related Entries
- [N+1 Query](n-plus-one-query.md) — caching batch-loaded data prevents N+1 query performance anti-pattern
- [Polyglot Persistence](../data/polyglot-persistence.md) — Redis as a caching layer is the most common polyglot persistence addition

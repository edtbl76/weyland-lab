---
id: database-sharding
tags: [pattern, database, backend, distributed-systems]
surfaces-at: [application-design, infrastructure-design]
related: [database-normalization, database-indexing, horizontal-vs-vertical-scaling, consistent-hashing, polyglot-persistence]
complexity: advanced
---

# Database Sharding

## What It Is
A horizontal scaling technique that partitions a database into multiple independent shards — each shard holds a subset of the data and runs on a separate database instance. No single machine holds all the data; queries are routed to the appropriate shard based on a shard key. Sharding enables databases to scale beyond the limits of a single machine for both storage and throughput. It is complex to implement and operate — exhaust vertical scaling, read replicas, and caching before reaching for sharding.

## When to Apply
- A single database instance cannot handle the data volume or write throughput even after vertical scaling, indexing, and caching
- Write throughput is the bottleneck — read replicas scale reads but not writes
- Multi-tenant architectures where tenant data must be isolated

## Key Concepts
- **Shard Key**: The column(s) used to determine which shard a row belongs to. Choosing the wrong shard key is the most common sharding mistake. A good shard key distributes data and queries evenly across shards; a bad one creates hot shards
- **Range Sharding**: Rows are assigned to shards based on value ranges of the shard key (e.g., user_id 1-1M → shard 1, 1M-2M → shard 2). Simple to understand; risk of uneven distribution if data is not uniformly distributed
- **Hash Sharding**: Hash the shard key to determine the shard. Even distribution by design; cross-shard range queries are expensive (cannot use shard key ordering)
- **Consistent Hashing**: A hash-based approach where adding or removing shards requires minimal data rebalancing. Standard for distributed caches; applicable to sharded databases
- **Cross-Shard Queries**: Queries that span multiple shards require scatter-gather — send the query to all relevant shards, collect results, merge. Expensive and complex. Design schemas and queries to minimize cross-shard operations
- **Cross-Shard Transactions**: ACID transactions across shards require distributed transactions (2PC) — complex and slow. Avoid by designing shard keys so that related data is co-located on the same shard
- **Hot Shards**: A shard receiving disproportionate traffic (e.g., all activity for one large customer). Leads to uneven resource utilization. Mitigate with composite shard keys or sub-sharding
- **Application-Level vs. Middleware Sharding**: Application-level sharding: the application routes to the correct shard explicitly. Middleware sharding: a proxy (Vitess for MySQL, Citus for PostgreSQL) handles routing transparently. Middleware is operationally simpler; application-level gives more control
- **Managed Sharding**: Cloud-managed sharded databases — Amazon DynamoDB, Google Spanner, CockroachDB — handle sharding, rebalancing, and cross-shard transactions transparently. Prefer managed over hand-rolled sharding when requirements allow

## In Practice
Method reaches for managed sharded databases (DynamoDB for key-value, Spanner for global ACID) before implementing application-level sharding on PostgreSQL. When sharding PostgreSQL is required, Citus is used as a transparent sharding layer. Shard key selection is reviewed carefully — tenant_id is the default for multi-tenant SaaS architectures.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Database Sharding**: Sharding is a last resort — it adds enormous operational complexity. Exhaust vertical scaling, read replicas, caching, and partitioning first. The shard key is the most important decision: it must distribute writes evenly and keep related data co-located to avoid cross-shard joins and transactions. Use managed sharded databases (DynamoDB, Spanner, CockroachDB) when possible — hand-rolled sharding is expensive to build and maintain. For multi-tenant SaaS, tenant_id is usually the right shard key — it co-locates all tenant data and isolates hot tenants. → `engineering-knowledge-repository/database-sharding.md`

## Related Entries
- [Database Normalization](database-normalization.md) — schema design affects which shard key choices are viable
- [Database Indexing](database-indexing.md) — each shard has its own indexes; index strategy applies per shard
- [Horizontal vs. Vertical Scaling](horizontal-vs-vertical-scaling.md) — sharding is the horizontal scaling pattern for write-heavy databases
- [Consistent Hashing](consistent-hashing.md) — consistent hashing minimizes data rebalancing when shard count changes
- [Polyglot Persistence](polyglot-persistence.md) — sharding complexity is a driver for choosing natively distributed databases over sharded relational DBs

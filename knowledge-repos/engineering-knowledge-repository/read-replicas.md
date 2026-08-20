---
id: read-replicas
tags: [pattern, database, backend, performance]
surfaces-at: [application-design, infrastructure-design]
related: [database-cost-optimization, mvcc, connection-pooling, database-transactions, horizontal-vs-vertical-scaling]
complexity: intermediate
---

# Read Replicas

## What It Is
Additional database instances that maintain a continuously synchronized copy of the primary database and serve read queries. Read replicas offload SELECT traffic from the primary, which can then dedicate its resources to writes and transactions. They are the standard scaling pattern for read-heavy workloads — cheaper than scaling the primary and enabling horizontal read scaling. Most managed database services (AWS RDS, Aurora, GCP Cloud SQL) support read replicas with minimal configuration.

## When to Apply
- Read-to-write ratio is high (reporting, analytics queries, read-heavy API endpoints)
- Primary database CPU or I/O is saturated by read traffic
- Reducing primary database cost by routing reads to cheaper replica instances
- Providing read capacity in additional regions for geographic distribution

## Key Concepts
- **Replication Lag**: Replicas are asynchronously updated — there is a small delay (milliseconds to seconds) between a write to the primary and its visibility on the replica. Applications must tolerate reading slightly stale data. Do not read from a replica when read-your-own-writes consistency is required immediately after a write
- **Read-Your-Own-Writes**: After a user writes data, reading back from a replica may return stale data if replication hasn't caught up. Solutions: route writes and immediate subsequent reads to the primary; use a session token to route the user's reads to the primary for a short window post-write
- **Replica Sizing**: Replicas don't need to match the primary's compute — size them for the read workload. Analytics replicas running complex queries may need more memory; OLTP read replicas can often be smaller than the primary
- **Aurora Read Replicas**: Aurora's shared storage architecture means replicas share the same storage as the primary — no replication lag for storage; only buffer cache lag. Up to 15 read replicas per Aurora cluster. Aurora Auto Scaling adds/removes read replicas based on CPU load
- **Connection Routing**: The application must route read queries to replicas. Options: explicit routing in the application data layer, a read/write splitting proxy (ProxySQL, RDS Proxy), or ORM-level read/write splitting (SQLAlchemy, Hibernate)
- **Replica for Backups and Analytics**: Running long analytics queries or backups on the primary blocks OLTP performance. Route these to a dedicated replica — analytics queries can run as long as needed without impacting users
- **Promoting a Replica**: In a failover scenario, a read replica can be promoted to primary. Planning promotion procedures and testing them is part of disaster recovery preparation

## In Practice
Method routes all reporting queries and analytics workloads to read replicas. A ProxySQL layer handles read/write splitting transparently for OLTP services. Aurora Auto Scaling manages replica count based on CPU. Analytics replicas are sized for memory-intensive queries; OLTP replicas match the primary for low-latency reads.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Read Replicas**: Read replicas are the first scaling lever for read-heavy workloads — cheaper and simpler than scaling the primary. Route reporting, analytics, and background read queries to replicas; keep writes and latency-sensitive reads on the primary. Account for replication lag — don't read from a replica immediately after a write if the user needs to see that write. Use a read/write splitting proxy (ProxySQL) to route transparently rather than coupling routing logic to application code. Size analytics replicas for query complexity, not primary parity. → `engineering-knowledge-repository/read-replicas.md`

## Related Entries
- [Database Cost Optimization](database-cost-optimization.md) — read replicas offload the primary, enabling smaller and cheaper primary instances
- [MVCC](mvcc.md) — replica reads use MVCC snapshots; replication lag affects snapshot freshness
- [Connection Pooling](connection-pooling.md) — connection pooling applies independently to primary and replica connections
- [Database Transactions](database-transactions.md) — transactions must run on the primary; replicas are read-only
- [Horizontal vs. Vertical Scaling](horizontal-vs-vertical-scaling.md) — read replicas are horizontal read scaling for databases

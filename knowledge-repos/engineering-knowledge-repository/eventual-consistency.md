---
id: eventual-consistency
tags: [principle, distributed-systems, backend]
surfaces-at: [application-design, functional-design]
related: [cap-theorem, event-driven-architecture, cqrs, outbox-pattern, saga-pattern, database-transactions]
complexity: intermediate
---

# Eventual Consistency

## What It Is
A consistency model used in distributed systems where, in the absence of new updates, all replicas of a piece of data will eventually converge to the same value. Unlike strong (linearizable) consistency — where every read reflects the most recent write — eventually consistent systems allow temporary divergence between replicas in exchange for higher availability, lower latency, and partition tolerance. Eventual consistency is not "weak" or "broken" consistency; it is the appropriate model for a large class of data where temporary staleness is acceptable and where strong consistency would require prohibitive coordination overhead or availability sacrifices.

## When to Apply
- High-availability distributed systems where availability > strict consistency (AP from CAP Theorem)
- Read-heavy workloads where returning slightly stale data is acceptable (product catalogs, user profiles, social feeds)
- Cross-service data synchronization via events where immediate consistency is not required
- Caching layers where the cache may lag the source of truth
- CQRS read models derived from event streams

## Key Concepts
- **Eventual vs. Strong Consistency**: Strong consistency guarantees that after a write, all subsequent reads see that write. Eventual consistency only guarantees convergence — reads may return stale data until replication catches up. The "eventually" window ranges from milliseconds to seconds in practice, rarely longer
- **Convergence Mechanisms**: How replicas converge:
  - *Last Write Wins (LWW)*: Conflicts resolved by timestamp — the latest write survives. Simple but loses data on concurrent writes
  - *Vector Clocks*: Track causality to detect concurrent writes and resolve conflicts deterministically
  - *CRDTs (Conflict-free Replicated Data Types)*: Data structures designed for automatic, lossless conflict resolution (counters, sets, maps) — merges are always valid
  - *Application-level reconciliation*: The application defines merge logic for conflicting writes (e.g., shopping cart unions)
- **Read-Your-Writes Consistency**: A common practical requirement — a user should always see their own writes, even in an eventually consistent system. Achieved by routing the same user's reads to the same replica, or by including a consistency token in responses. DynamoDB, Cassandra, and others provide this as an option
- **Monotonic Read Consistency**: Once a reader has seen a value, they should never see an older value. Prevents "time traveling" UI where a page refresh shows older data. Can be achieved through session affinity to replicas
- **Stale Reads in Practice**: In well-designed AP systems, the staleness window is typically milliseconds to low seconds. For most application data (product listings, notification counts, social feeds), this is imperceptible. For financial balances and inventory counts, it is not acceptable — use CP for those
- **Event-Driven Eventual Consistency**: The most common pattern in microservices — services publish domain events; consumers update their local state asynchronously. The consumer's state eventually reflects the producer's state. The outbox pattern ensures reliable event delivery
- **Compensating Transactions**: When an eventually consistent operation is discovered to be invalid after the fact (a coupon was applied to an order but later found expired), compensating transactions undo or adjust the outcome. This is the saga pattern

## In Practice
Method's CQRS read models are eventually consistent — write events are published to an event stream and the read model is updated asynchronously. Product catalog data in CDN and cache layers is eventually consistent with a defined max-stale TTL. User account balance and payment data use strong consistency (PostgreSQL with synchronous replication). Cross-service communication via events is documented with explicit consistency windows in service contracts.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Eventual Consistency**: Most application data doesn't require strong consistency — it requires "good enough" consistency, and eventual consistency provides it at dramatically lower cost and higher availability. The mistake is applying strong consistency everywhere out of habit, paying the latency and availability tax for data that doesn't need it. Design per data type: financial transactions and inventory counts need CP; product catalogs, user feeds, and notification counts are excellent AP candidates. Document your consistency model per data type — "eventually consistent with max 5s staleness" is a concrete SLA, not a vague excuse. → `engineering-knowledge-repository/eventual-consistency.md`

## Related Entries
- [CAP Theorem](cap-theorem.md) — eventual consistency is the practical expression of the AP tradeoff in CAP Theorem
- [Event-Driven Architecture](event-driven-architecture.md) — event-driven systems are the primary mechanism for achieving eventual consistency between services
- [CQRS](cqrs.md) — CQRS read models are typically eventually consistent, derived from the event stream
- [Outbox Pattern](outbox-pattern.md) — the outbox pattern ensures reliable event delivery that drives eventual consistency
- [Saga Pattern](saga-pattern.md) — sagas manage multi-step distributed operations under eventual consistency with compensating transactions
- [Database Transactions](database-transactions.md) — ACID transactions provide the strong consistency alternative; understanding both is required to choose correctly

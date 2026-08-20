---
id: cap-theorem
tags: [principle, distributed-systems, backend]
surfaces-at: [application-design, functional-design]
related: [eventual-consistency, database-transactions, distributed-locks, microservices, saga-pattern, database-sharding]
complexity: intermediate
---

# CAP Theorem

## What It Is
A fundamental theorem in distributed systems, proven by Eric Brewer, stating that a distributed data store can provide at most two of three guarantees simultaneously: **Consistency** (every read receives the most recent write or an error), **Availability** (every request receives a response, though it may not be the most recent), and **Partition Tolerance** (the system continues operating when network partitions occur). Because network partitions are a reality in any distributed system, the practical choice is between CP (consistency over availability) and AP (availability over consistency) — not a free choice between all three. CAP Theorem is the foundational framework for understanding why distributed systems make different tradeoffs and why "strong consistency everywhere" is not achievable in distributed architectures.

## When to Apply
- Designing distributed data stores or choosing between database technologies
- Evaluating tradeoffs when a service spans multiple nodes, regions, or data centers
- Explaining why eventual consistency is the default in distributed systems, not a compromise
- When stakeholders ask "why can't the system always return the latest data?"
- Multi-region deployment decisions where partition tolerance requirements force consistency tradeoffs

## Key Concepts
- **Consistency (C)**: Every read sees the most recent write. Not eventual consistency — strict linearizability. All nodes see the same data at the same time. Example: after writing a value to node A, any read from node B immediately returns that value
- **Availability (A)**: Every request gets a response (not an error). The response may not contain the most recent data, but the system always responds. Example: a read during a network partition returns cached or potentially stale data rather than an error
- **Partition Tolerance (P)**: The system continues to function when network partitions occur (messages between nodes are lost or delayed). In any real distributed system over a network, partitions will happen — making P effectively mandatory. The theorem therefore reduces to: during a partition, choose C or A
- **CP Systems**: Sacrifice availability during a network partition. When a partition occurs, the system returns an error rather than potentially stale data. Examples: HBase, Zookeeper, etcd, traditional relational databases with strict consistency (PostgreSQL in synchronous replication mode). Right for: financial systems, coordination services, anything where stale data is unacceptable
- **AP Systems**: Sacrifice strict consistency during a partition. The system remains available and returns its best available data (which may be stale). Eventually, when the partition heals, nodes converge. Examples: Cassandra, DynamoDB (by default), CouchDB. Right for: shopping carts, social feeds, DNS, systems where temporary staleness is acceptable
- **CA Systems**: Consistency + Availability without partition tolerance. This only works on a single node or when partitions literally cannot occur (same datacenter, single machine). Not meaningful for distributed systems
- **PACELC Extension**: An extension of CAP that also considers the latency-consistency tradeoff even when no partition exists. Even without a partition, distributed systems must choose between low latency (return local data) and consistency (wait for global agreement). PACELC = If Partition: A or C; Else: L (latency) or C
- **Eventual Consistency**: The AP tradeoff in practice. The system is eventually consistent — after partitions heal and writes propagate, all nodes will converge to the same state. The time to convergence varies from milliseconds to seconds depending on the system

## In Practice
Method's backend services primarily use PostgreSQL (CP — strong consistency) for transactional data where consistency is critical. DynamoDB with eventual consistency is used for high-volume read-heavy workloads (session data, event streams) where temporary staleness is acceptable. When designing features that span services, the CAP tradeoff informs whether cross-service coordination requires distributed transactions (expensive, limits availability) or eventual consistency patterns (saga, outbox).

## Engineering Knowledge Statement
💡 **Engineering Knowledge — CAP Theorem**: In distributed systems, partition tolerance is not optional — networks fail, nodes go down, datacenters lose connectivity. The real choice is: during a partition, do you return an error (CP) or return potentially stale data (AP)? This is a business decision, not just a technical one. Financial transactions: CP. Shopping cart contents: AP. Most systems need both CP and AP for different data — design your consistency model per data type, not globally. Eventual consistency is not "bad consistency" — it's the correct tradeoff for high-availability distributed data. → `engineering-knowledge-repository/cap-theorem.md`

## Related Entries
- [Eventual Consistency](eventual-consistency.md) — the AP tradeoff in practice; how systems converge after partitions
- [Database Transactions](database-transactions.md) — ACID transactions provide CP guarantees; distributed transactions extend this at high cost
- [Distributed Locks](distributed-locks.md) — distributed locking provides coordination at the cost of availability during partitions
- [Microservices](microservices.md) — microservice architectures require explicit CAP tradeoff decisions per service
- [Saga Pattern](saga-pattern.md) — sagas manage distributed transactions without requiring CP consistency across services
- [Database Sharding](database-sharding.md) — sharding distributes data across nodes, forcing explicit CAP tradeoff decisions

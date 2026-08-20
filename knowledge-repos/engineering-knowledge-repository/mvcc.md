---
id: mvcc
tags: [pattern, concurrency, database, backend]
surfaces-at: [application-design, functional-design]
related: [optimistic-locking, pessimistic-locking, database-transactions, deadlocks, connection-pooling]
complexity: intermediate
---

# MVCC (Multi-Version Concurrency Control)

## What It Is
A concurrency control mechanism used by databases (PostgreSQL, MySQL InnoDB, Oracle, CockroachDB) to allow readers and writers to operate concurrently without blocking each other. Rather than locking rows for reads, MVCC maintains multiple versions of each row — readers see a consistent snapshot of the database as it existed at the start of their transaction, while writers create new versions. Reads never block writes; writes never block reads. This enables high concurrency with strong consistency guarantees.

## When to Apply
- Understanding why PostgreSQL reads don't block writes (and vice versa)
- Diagnosing table bloat and `VACUUM` issues in PostgreSQL
- Choosing isolation levels for transactions
- Designing applications that require consistent point-in-time reads (reporting, analytics)

## Key Concepts
- **Row Versioning**: Each row modification creates a new version with a transaction ID timestamp. Old versions are retained until no active transaction needs them. Readers read the version visible at their transaction start time
- **Snapshot Isolation**: Each transaction sees a consistent snapshot of the database as of its start time — subsequent commits by other transactions are invisible. Prevents dirty reads and non-repeatable reads. The default isolation level in PostgreSQL (`READ COMMITTED` shows committed data as of each statement; `REPEATABLE READ` fixes the snapshot at transaction start)
- **No Read Locks**: Because readers see a historical snapshot, they never need to lock rows. A long-running report query doesn't block concurrent writes. This is the key benefit of MVCC over lock-based concurrency
- **Write Conflicts**: Writers do conflict with each other. The first writer to commit wins; subsequent writers to the same row must either retry or fail (depending on isolation level)
- **Dead Tuples and VACUUM**: Old row versions (dead tuples) accumulate as rows are updated and deleted. PostgreSQL's `VACUUM` process reclaims this space. High write rates require frequent autovacuum. Table bloat from uninvacuumed dead tuples causes performance degradation and, in extreme cases, transaction ID wraparound
- **Transaction ID Wraparound**: PostgreSQL uses 32-bit transaction IDs that wrap around after ~2 billion transactions. Failure to VACUUM before wraparound causes database unavailability. Monitor transaction age; ensure autovacuum runs regularly on high-write tables
- **Long-Running Transactions**: A long-running transaction holds a snapshot from its start time — prevents VACUUM from reclaiming any dead tuples created after that snapshot. In high-write systems, long transactions cause unbounded bloat. Monitor and kill unexpectedly long transactions
- **Serializable Snapshot Isolation (SSI)**: PostgreSQL's `SERIALIZABLE` isolation level extends snapshot isolation to prevent serialization anomalies (write skew) using predicate locking. Strong guarantee; small performance overhead

## In Practice
Method PostgreSQL databases use `READ COMMITTED` for OLTP workloads and `REPEATABLE READ` for operations requiring consistent snapshots (batch processing, reporting). Autovacuum settings are tuned for high-write tables. Long-running transactions are monitored and alerted via `pg_stat_activity`. Transaction ID age is monitored as a critical database health metric.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — MVCC**: MVCC is why PostgreSQL reads don't block writes — readers see a historical snapshot; no row locking required. The cost is dead tuple accumulation — autovacuum must keep up with your write rate or table bloat degrades performance. Long-running transactions are the enemy of MVCC: they prevent VACUUM from reclaiming dead tuples. Monitor `pg_stat_activity` for long transactions and kill them. Watch transaction ID age — wraparound is a hard availability failure. Choose `REPEATABLE READ` when you need a consistent snapshot across multiple queries in a transaction (reporting, batch jobs). → `engineering-knowledge-repository/mvcc.md`

## Related Entries
- [Optimistic Locking](optimistic-locking.md) — optimistic locking at the application layer complements MVCC at the database layer
- [Pessimistic Locking](pessimistic-locking.md) — `SELECT FOR UPDATE` uses row-level write locks even in MVCC databases
- [Database Transactions](database-transactions.md) — isolation levels determine how MVCC snapshots are scoped
- [Deadlocks](deadlocks.md) — MVCC reduces but doesn't eliminate deadlocks — write conflicts can still deadlock
- [Connection Pooling](connection-pooling.md) — idle connections holding open transactions block VACUUM; pool configuration affects transaction lifetimes

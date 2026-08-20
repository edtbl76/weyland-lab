---
id: database-transactions
tags: [pattern, database, backend, concurrency]
surfaces-at: [functional-design, application-design]
related: [mvcc, optimistic-locking, pessimistic-locking, deadlocks, connection-pooling, saga-pattern]
complexity: intermediate
---

# Database Transactions

## What It Is
A database transaction is a sequence of operations treated as a single atomic unit — either all operations commit successfully or all are rolled back, leaving the database in a consistent state. Transactions are defined by the ACID properties and are the fundamental mechanism for maintaining data integrity in relational databases. Understanding transaction isolation levels is essential for writing correct concurrent database code.

## When to Apply
- Any multi-step database operation where partial completion would leave data in an inconsistent state
- Coordinating reads and writes that must see a consistent snapshot
- Any financial, inventory, or state-change operation where atomicity is required

## Key Concepts
- **ACID Properties**:
  - *Atomicity*: All operations in a transaction succeed or all are rolled back — no partial commits
  - *Consistency*: Transactions move the database from one valid state to another — constraints and rules are enforced
  - *Isolation*: Concurrent transactions behave as if they executed serially — the degree of isolation is configurable
  - *Durability*: Committed transactions survive system failures — written to durable storage
- **Isolation Levels** (weakest to strongest):
  - *Read Uncommitted*: Reads uncommitted changes from other transactions (dirty reads). Rarely used
  - *Read Committed*: Reads only committed data. Default in PostgreSQL, Oracle. Prevents dirty reads; allows non-repeatable reads
  - *Repeatable Read*: Same row read twice returns the same value within a transaction. Prevents dirty and non-repeatable reads; may allow phantom reads. Default in MySQL InnoDB
  - *Serializable*: Full isolation — transactions behave as if executed one at a time. Prevents all anomalies; highest contention and overhead
- **Common Anomalies**:
  - *Dirty Read*: Reading uncommitted data from another transaction
  - *Non-Repeatable Read*: Same row returns different values when read twice (another transaction committed between reads)
  - *Phantom Read*: A query returns different rows when executed twice (another transaction inserted/deleted rows)
  - *Write Skew*: Two transactions read overlapping data, make disjoint writes based on stale reads — each write is valid individually but combined they violate a constraint
- **Savepoints**: Partial rollback points within a transaction — roll back to a savepoint without aborting the entire transaction
- **Transaction Scope in Applications**: Keep transactions as short as possible — long-running transactions hold locks, block VACUUM (PostgreSQL), and increase deadlock risk. Don't include user interaction or network calls within a transaction
- **Distributed Transactions**: Transactions spanning multiple databases or services. Two-phase commit (2PC) provides atomicity but is slow and operationally fragile. The Saga pattern is the modern alternative — see Saga Pattern entry
- **ORMs and Transactions**: ORMs wrap operations in transactions implicitly (unit-of-work pattern). Understand when your ORM opens and commits transactions — unexpected implicit commits cause bugs

## In Practice
Method applications use `READ COMMITTED` for standard OLTP operations. `REPEATABLE READ` is used for batch jobs requiring consistent snapshots. Transactions are scoped tightly around the database operations they protect — no network calls inside transactions. ORM transaction boundaries are explicit, not implicit. Long transactions are monitored via `pg_stat_activity`.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Database Transactions**: Keep transactions short — every open transaction holds locks and blocks VACUUM. Choose the weakest isolation level that provides correct behavior: `READ COMMITTED` handles most OLTP cases; `REPEATABLE READ` for batch jobs needing consistent snapshots; `SERIALIZABLE` only when write skew is a real concern. Never include network calls or user interaction inside a transaction. Understand your ORM's transaction boundaries — implicit transactions are a common source of subtle bugs. For operations spanning multiple services, use the Saga pattern instead of distributed 2PC. → `engineering-knowledge-repository/database-transactions.md`

## Related Entries
- [MVCC](mvcc.md) — PostgreSQL implements isolation levels through MVCC rather than locking
- [Optimistic Locking](optimistic-locking.md) — application-level concurrency control that works within transaction boundaries
- [Pessimistic Locking](pessimistic-locking.md) — `SELECT FOR UPDATE` acquires row locks within transactions
- [Deadlocks](deadlocks.md) — transactions acquiring multiple locks are the primary source of database deadlocks
- [Connection Pooling](connection-pooling.md) — connection pools manage the database connections on which transactions run
- [Saga Pattern](saga-pattern.md) — the alternative to distributed transactions for multi-service operations

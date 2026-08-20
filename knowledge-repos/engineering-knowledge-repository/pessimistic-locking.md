---
id: pessimistic-locking
tags: [pattern, data, database, backend]
surfaces-at: [functional-design, application-design]
related: [optimistic-locking, database-indexing, connection-pooling, cqrs]
complexity: intermediate
---

# Pessimistic Locking

## What It Is
A concurrency control strategy that prevents conflicts by acquiring an exclusive lock on a record before reading it, holding that lock for the duration of the transaction. Other transactions that attempt to read or write the locked record must wait. Pessimistic locking assumes conflicts are likely and pays the cost upfront (blocking) rather than at commit time (retry). Implemented in SQL via `SELECT ... FOR UPDATE`.

## When to Apply
- High-contention scenarios where multiple concurrent writers frequently target the same records
- Operations where a conflict would be costly to retry — long workflows, external side effects triggered mid-transaction
- Financial transactions where the business logic depends on a consistent read followed immediately by a write
- Short transactions where the lock is held briefly — the blocking window is small

## When Not to Apply
- Read-heavy workloads where conflicts are rare — pessimistic locking serializes reads unnecessarily
- Long-running transactions that hold locks across user think time or network round trips — causes severe contention
- Distributed systems without a shared database that can coordinate locks — pessimistic locking requires a central lock authority

## Key Concepts
- **`SELECT ... FOR UPDATE`**: The SQL statement that acquires a row-level exclusive lock. The row is locked until the transaction commits or rolls back. Blocked transactions queue and wait
- **`SELECT ... FOR SHARE`**: Acquires a shared lock — multiple readers can hold it simultaneously, but writers must wait. Use when you need a consistent read without preventing other reads
- **`SKIP LOCKED`**: PostgreSQL/MySQL extension — `SELECT ... FOR UPDATE SKIP LOCKED`. Returns only unlocked rows; skips rows currently locked by other transactions. Used for job queues to allow multiple workers to dequeue without blocking each other
- **`NOWAIT`**: `SELECT ... FOR UPDATE NOWAIT` — fails immediately if the row is locked rather than waiting. Useful when blocking is unacceptable and the application prefers to fail fast and retry
- **Deadlock**: Two transactions each holding a lock the other needs. Databases detect and resolve deadlocks by rolling back one transaction. Application code must handle deadlock errors and retry
- **Lock Granularity**: Row-level locks (most common, least contention), page-level locks, table-level locks. Most production databases use row-level locking by default
- **Transaction Scope**: Locks are held for the duration of the database transaction — keep transactions short to minimize blocking window

## In Practice
Method uses `SELECT ... FOR UPDATE` for inventory reservation, seat booking, and financial ledger operations where the correctness guarantee justifies the serialization cost. `SKIP LOCKED` is used for task queue implementations where multiple workers consume from a shared queue. Transactions are kept short — no user interaction or external API calls inside a locked transaction.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Pessimistic Locking**: Use `SELECT ... FOR UPDATE` when conflicts are likely and retrying is expensive. The row is locked until the transaction ends — keep transactions short or you'll cause queuing. Use `SKIP LOCKED` for job queues so multiple workers can pull rows without blocking each other. Use `NOWAIT` when you prefer immediate failure over waiting. Deadlocks are possible — always handle and retry. Prefer optimistic locking for read-heavy, low-contention scenarios; pessimistic for write-heavy, high-contention ones. Never hold a pessimistic lock across a network call or user interaction. → `engineering-knowledge-repository/pessimistic-locking.md`

## Related Entries
- [Optimistic Locking](optimistic-locking.md) — the alternative strategy; assumes conflicts are rare and detects at write time
- [Database Indexing](database-indexing.md) — the locked row must be found efficiently; poor indexing multiplies lock contention
- [Connection Pooling](connection-pooling.md) — locked transactions hold connections; pool exhaustion under contention is a common failure mode
- [CQRS](cqrs.md) — pessimistic locking is used on the command side when consistency guarantees require it

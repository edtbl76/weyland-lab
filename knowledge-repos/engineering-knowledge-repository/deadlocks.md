---
id: deadlocks
tags: [pattern, concurrency, backend]
surfaces-at: [functional-design, code-generation]
related: [race-conditions, pessimistic-locking, distributed-locks, database-transactions]
complexity: intermediate
---

# Deadlocks

## What It Is
A situation where two or more threads are permanently blocked waiting for each other to release resources. Thread A holds lock X and waits for lock Y; Thread B holds lock Y and waits for lock X — neither can proceed. Deadlocks silently freeze processes with no error message. They are difficult to reproduce because they depend on specific timing and interleaving. Deadlocks occur in both in-process locking (mutexes) and distributed systems (database row locks, distributed locks).

## When to Apply
- Designing any code that acquires multiple locks
- Reviewing database transaction logic that touches multiple rows or tables
- Any system using distributed locks across multiple resources

## Key Concepts
- **Four Necessary Conditions (Coffman Conditions)**: All four must hold for a deadlock to occur. Eliminating any one prevents deadlocks:
  1. *Mutual Exclusion*: Resources cannot be shared
  2. *Hold and Wait*: Threads hold resources while waiting for others
  3. *No Preemption*: Resources cannot be forcibly taken
  4. *Circular Wait*: A circular chain of threads each waiting for the next
- **Prevention — Lock Ordering**: Always acquire multiple locks in a globally consistent order. If all threads acquire lock A before lock B, circular wait is impossible. Document and enforce the lock acquisition order
- **Prevention — Lock Timeout**: Attempt to acquire a lock with a timeout; if it fails, release all held locks and retry after a backoff. Breaks the hold-and-wait condition. Requires idempotent retry logic
- **Prevention — Avoid Holding Locks Across I/O**: Never hold a mutex while performing I/O, network calls, or other slow operations — dramatically reduces the window for deadlocks and contention
- **Detection — Timeout-Based**: Database systems detect deadlocks by identifying circular waits in the lock graph and killing one of the transactions. PostgreSQL detects and reports deadlocks automatically
- **Livelock**: Threads are not blocked but continuously change state in response to each other without making progress — similar to two people stepping aside for each other in a hallway. Prevent with randomized backoff
- **Database Deadlocks**: Transaction A locks row 1, then row 2; Transaction B locks row 2, then row 1. Prevention: access rows in consistent order across transactions; keep transactions short; use optimistic locking where possible
- **Deadlock vs. Starvation**: Deadlock — no progress for involved threads. Starvation — a thread makes no progress because others always win access to a shared resource. Different root causes; different solutions

## In Practice
Method codebases prevent deadlocks through lock ordering documentation, timeouts on lock acquisition, and keeping critical sections short. Database deadlocks are caught by PostgreSQL's automatic detection and retried with exponential backoff at the application level. Code reviews flag any code that acquires multiple locks without following the documented ordering.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Deadlocks**: Prevent deadlocks by always acquiring multiple locks in a globally consistent order — document it and enforce it in code review. Never hold a lock while performing I/O or network calls. Add timeouts to lock acquisition and retry with backoff rather than waiting indefinitely. For database deadlocks, PostgreSQL detects them automatically and aborts one transaction — your application must catch and retry the aborted transaction. Keep transactions short to minimize the window for deadlock formation. → `engineering-knowledge-repository/deadlocks.md`

## Related Entries
- [Race Conditions](race-conditions.md) — the locks used to prevent race conditions can introduce deadlocks if misused
- [Pessimistic Locking](pessimistic-locking.md) — pessimistic locking with multiple resources is a common deadlock source
- [Distributed Locks](distributed-locks.md) — deadlocks can occur across distributed lock acquisitions
- [Database Transactions](database-transactions.md) — transaction isolation and row locking are the primary source of database-level deadlocks

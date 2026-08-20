---
id: distributed-locks
tags: [pattern, concurrency, distributed-systems, backend]
surfaces-at: [application-design, functional-design]
related: [race-conditions, deadlocks, optimistic-locking, pessimistic-locking, idempotency]
complexity: advanced
---

# Distributed Locks

## What It Is
A synchronization mechanism that coordinates exclusive access to a shared resource across multiple processes or service instances running on different machines. Standard in-process mutexes only work within a single process — when multiple instances of a service run concurrently, a distributed lock is required to ensure only one instance performs a critical operation at a time. Common use cases: preventing duplicate cron job execution, coordinating leader election, serializing access to a shared external resource.

## When to Apply
- Preventing multiple service instances from executing the same scheduled job simultaneously
- Leader election — only one instance should perform a role at a time
- Coordinating writes to a shared external resource that doesn't support native transactions
- Exactly-once processing guarantees in distributed systems

## Key Concepts
- **Redis-Based Locking (Redlock)**: Acquire a lock by setting a Redis key with `SET key value NX PX ttl` — set only if not exists, with a TTL. Release by deleting the key only if the value matches (Lua script for atomicity). TTL prevents permanent lock if the holder crashes
- **Redlock Algorithm**: For higher reliability, acquire the lock on a majority of N independent Redis nodes. If a majority acquired within a time window, the lock is held. Controversial — Martin Kleppmann identified safety issues under clock drift; most practitioners use single-node Redis with fencing tokens for typical use cases
- **Fencing Token**: A monotonically increasing token issued with the lock. The token is passed to the protected resource with each operation. The resource rejects operations with tokens lower than the highest seen — prevents stale lock holders from causing damage after their lock expired
- **Lock TTL and Lease Renewal**: Set TTL longer than the expected operation duration. For long operations, renew the lease before expiry (heartbeat). If the process dies, the TTL ensures eventual lock release — no manual cleanup required
- **ZooKeeper / etcd**: Consensus-based distributed lock implementations — more operationally complex than Redis but provide stronger guarantees. ZooKeeper ephemeral znodes release automatically when the client disconnects. Used in systems already running ZooKeeper/etcd (Kafka, Kubernetes)
- **Database Advisory Locks**: PostgreSQL `pg_advisory_lock` — application-level locks stored in the database. Simpler than Redis for systems already using Postgres. Released automatically on session end
- **Dangers of Distributed Locks**:
  - A process can hold a lock, pause (GC, network partition), lock expires, another process acquires it, original process resumes thinking it still holds the lock — use fencing tokens to protect against this
  - Distributed locks are advisory — every participant must check and respect them
  - Do not use distributed locks as a substitute for idempotency — always design operations to be safe to retry
- **Idempotency as an Alternative**: Often the correct solution is to make the operation idempotent rather than use a distributed lock. Idempotency is more resilient and avoids lock contention entirely

## In Practice
Method uses Redis `SET NX PX` for distributed cron job deduplication and short-duration critical sections. PostgreSQL advisory locks are used for database-level coordination within the same database. Fencing tokens are implemented for any lock protecting an external resource. Long-running operations use idempotency keys rather than locks wherever possible.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Distributed Locks**: Before reaching for a distributed lock, ask whether idempotency solves the problem — an idempotent operation is safer and more resilient than a lock. For Redis-based locks, use `SET NX PX` with a TTL and verify the value on release (Lua script). Use fencing tokens when the protected resource must reject stale operations from expired lock holders. Never assume a lock is still held after a network pause or GC stop — design for the possibility that the lock expired while you were doing work. Prefer PostgreSQL advisory locks for systems already on Postgres; simpler than Redis with sufficient guarantees for most use cases. → `engineering-knowledge-repository/distributed-locks.md`

## Related Entries
- [Race Conditions](race-conditions.md) — distributed locks prevent race conditions across multiple service instances
- [Deadlocks](deadlocks.md) — acquiring multiple distributed locks without ordering can cause distributed deadlocks
- [Optimistic Locking](optimistic-locking.md) — optimistic locking is often preferable to distributed locks for database-level coordination
- [Pessimistic Locking](pessimistic-locking.md) — pessimistic locking at the database level can substitute for distributed locks in single-database scenarios
- [Idempotency](idempotency.md) — idempotency is frequently a better alternative to distributed locks

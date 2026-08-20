---
id: read-write-locks
tags: [pattern, concurrency, backend]
surfaces-at: [functional-design, code-generation]
related: [race-conditions, deadlocks, thread-pools, connection-pooling]
complexity: intermediate
---

# Read-Write Locks

## What It Is
A synchronization primitive that allows multiple threads to read shared data concurrently, while ensuring exclusive access for writes. A standard mutex serializes all access — one reader at a time, even when reads are safe to parallelize. A read-write lock (RWLock) distinguishes between these two access patterns: many threads can hold the read lock simultaneously; only one thread can hold the write lock, and only when no readers are active. This improves throughput for read-heavy workloads where writes are infrequent.

## When to Apply
- Shared data structures that are read frequently but written infrequently (caches, configuration, routing tables, in-memory indexes)
- When profiling shows mutex contention on a read-heavy resource is a bottleneck
- In-memory state that multiple threads query concurrently

## Key Concepts
- **Read Lock (Shared Lock)**: Multiple threads can hold the read lock simultaneously. Acquiring a read lock blocks only if a write lock is held
- **Write Lock (Exclusive Lock)**: Only one thread can hold the write lock. Acquiring a write lock blocks until all existing readers release and no other writer holds the lock
- **Writer Starvation**: If readers continuously acquire the lock, writers may wait indefinitely. Most implementations give writers priority once they are waiting — new readers block until the pending writer has proceeded
- **Upgrade Deadlock**: Attempting to upgrade a held read lock to a write lock while another thread also holds a read lock causes deadlock — both wait for the other to release. Never upgrade a read lock; release and reacquire as a write lock
- **Language Support**:
  - Python: `threading.RLock` is a reentrant mutex; use `threading.Lock` directly or `asyncio.Lock` for async. For true RWLock: `rwlock` third-party library
  - Java: `java.util.concurrent.locks.ReentrantReadWriteLock` — standard library, widely used
  - Go: `sync.RWMutex` — `RLock()`/`RUnlock()` for reads, `Lock()`/`Unlock()` for writes
  - Rust: `std::sync::RwLock` — compile-time borrow checker enforces correct usage
- **When NOT to Use**: If writes are frequent, the write lock serializes access and the RWLock provides little benefit over a mutex — with added complexity. Profile first; only reach for RWLock when read contention on a standard mutex is a measured problem
- **Fairness**: Choose implementations that are fair to writers — unfair RWLocks can starve writers under sustained read load

## In Practice
Method uses `ReentrantReadWriteLock` in Java for in-memory caches and configuration objects that are read on every request but updated infrequently. Go services use `sync.RWMutex` for shared routing tables and connection registries. Standard mutexes are used by default; RWLocks are introduced only when read contention is a measured bottleneck.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Read-Write Locks**: Use RWLocks for read-heavy shared state where standard mutex contention is a measured bottleneck — not as a default. Multiple concurrent readers are safe; only writes require exclusivity. Never attempt to upgrade a read lock to a write lock — release the read lock first to avoid deadlock. Watch for writer starvation under sustained read load; choose implementations that give waiting writers priority. Go's `sync.RWMutex` and Java's `ReentrantReadWriteLock` are the idiomatic choices. → `engineering-knowledge-repository/read-write-locks.md`

## Related Entries
- [Race Conditions](race-conditions.md) — RWLocks are a synchronization primitive for preventing read-write and write-write race conditions
- [Deadlocks](deadlocks.md) — lock upgrade attempts (read → write) are a deadlock source specific to RWLocks
- [Thread Pools](thread-pools.md) — thread pool workers sharing in-memory state benefit from RWLocks on read-heavy data
- [Connection Pooling](connection-pooling.md) — connection pool registries are a common RWLock use case

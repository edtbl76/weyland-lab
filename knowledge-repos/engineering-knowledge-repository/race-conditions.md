---
id: race-conditions
tags: [pattern, concurrency, backend]
surfaces-at: [functional-design, code-generation]
related: [deadlocks, optimistic-locking, pessimistic-locking, distributed-locks, thread-pools, async-programming-patterns]
complexity: intermediate
---

# Race Conditions and Thread Safety

## What It Is
A race condition occurs when the correctness of a program depends on the relative timing or interleaving of multiple threads or processes accessing shared mutable state. When two threads read-modify-write the same value without coordination, one update can silently overwrite the other — producing corrupt state with no error. Thread safety is the property of code that behaves correctly when called from multiple concurrent threads. Race conditions are among the hardest bugs to reproduce and diagnose because they are timing-dependent.

## When to Apply
- Any code that shares mutable state across threads, goroutines, or async tasks
- Code reviews touching shared data structures, counters, caches, or session state
- Designing concurrent data pipelines or background job processors

## Key Concepts
- **Critical Section**: Code that accesses shared mutable state. Only one thread should execute a critical section at a time. Protect with a mutex (mutual exclusion lock)
- **Mutex (Lock)**: A synchronization primitive that allows only one thread to hold it at a time. `acquire()` blocks until the lock is available; `release()` unblocks a waiting thread. Use `try/finally` or context managers to guarantee release
- **Atomic Operations**: Operations guaranteed to complete without interruption — no thread can observe a partial state. CPU-level atomics (`AtomicInteger`, `atomic_int`) for counters; avoids mutex overhead for simple increment/compare-and-swap operations
- **Immutability**: Immutable objects are inherently thread-safe — shared read-only state requires no synchronization. Prefer immutable data structures where possible; only introduce mutability where necessary
- **Thread-Local Storage**: Data scoped to a single thread — not shared, so no synchronization needed. Python `threading.local()`, Java `ThreadLocal`. Useful for per-request context (database connections, user identity)
- **Visibility**: In Java/JVM, changes made by one thread may not be visible to others due to CPU caching and reordering. `volatile` ensures visibility; `synchronized` ensures both visibility and mutual exclusion
- **Check-Then-Act**: A common race condition pattern — check a condition then act on it, but the condition changes between check and act. Protect the check and the act as an atomic unit
- **Concurrent Data Structures**: Thread-safe collections — `ConcurrentHashMap` (Java), `queue.Queue` (Python), channels (Go). Use these instead of wrapping standard collections in a mutex where possible — better performance and correctness guarantees
- **Testing for Race Conditions**: Deterministic unit tests rarely expose race conditions. Use race detectors (`go race`, ThreadSanitizer for C/C++) and stress testing with high concurrency. Java's `jcstress` for concurrency-specific testing

## In Practice
Method codebases use language-native thread-safe primitives: Python `threading.Lock` and `queue.Queue`, Java `ConcurrentHashMap` and `AtomicLong`. Shared mutable state is minimized by design — stateless service handlers avoid the problem entirely. Code reviews flag any bare read-modify-write on shared state without synchronization.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Race Conditions**: The safest approach is no shared mutable state — stateless handlers and immutable data eliminate the problem. When shared state is required, use atomic operations for simple counters and mutexes for critical sections. Always use language-native concurrent collections rather than locking a non-thread-safe collection. Check-then-act patterns are a common race condition source — protect the entire check+act as an atomic unit. Race conditions don't reproduce consistently — use race detectors in CI, not just manual testing. → `engineering-knowledge-repository/race-conditions.md`

## Related Entries
- [Deadlocks](deadlocks.md) — improper use of mutexes to prevent race conditions can introduce deadlocks
- [Optimistic Locking](optimistic-locking.md) — optimistic locking handles race conditions on shared data without blocking
- [Pessimistic Locking](pessimistic-locking.md) — pessimistic locking prevents race conditions by blocking concurrent access
- [Distributed Locks](distributed-locks.md) — race conditions across multiple service instances require distributed locks
- [Thread Pools](thread-pools.md) — thread pools share work queues and require thread-safe access patterns
- [Async Programming Patterns](async-programming-patterns.md) — async concurrency has its own forms of race conditions

---
id: thread-pools
tags: [pattern, concurrency, backend]
surfaces-at: [nfr-requirements, functional-design]
related: [race-conditions, async-programming-patterns, bulkhead-pattern, timeout-patterns]
complexity: intermediate
---

# Thread Pools

## What It Is
A concurrency pattern that maintains a fixed set of worker threads to execute tasks from a queue, rather than creating and destroying a thread per task. Thread creation is expensive — pools amortize that cost. More importantly, pools bound the maximum number of concurrent threads, preventing unbounded thread creation from exhausting memory and CPU. Thread pools are the execution model behind most web servers, database connection pools, and async work dispatchers.

## When to Apply
- Processing concurrent tasks where per-task thread creation would be expensive
- Bounding concurrency to prevent resource exhaustion under load
- Offloading CPU-bound or blocking work from event loops or request-handling threads
- Any background task processing that must not starve the main request path

## Key Concepts
- **Core and Maximum Pool Size**: Core threads are kept alive even when idle. Additional threads are created up to the maximum when the queue is full. Threads above core count are terminated after an idle timeout. Choose core size based on expected sustained load; maximum size as the burst ceiling
- **Work Queue**: Tasks are submitted to a queue and picked up by available threads. Queue types:
  - *Bounded queue*: Fixed capacity — rejects or blocks when full. Provides backpressure
  - *Unbounded queue*: No limit — tasks accumulate in memory under sustained overload. Dangerous — can cause OOM
  - Always use bounded queues in production
- **Rejection Policy**: What happens when the pool is at maximum capacity and the queue is full. Options: throw exception, block caller, discard task, discard oldest task, execute in caller thread. Choose based on the cost of dropped vs. delayed tasks
- **Sizing Thread Pools**:
  - *CPU-bound tasks*: Pool size = number of CPU cores (or cores + 1). More threads than cores causes context switching overhead
  - *I/O-bound tasks*: Pool size = cores × (1 + wait_time / service_time). More threads can be productive because they spend time waiting for I/O
  - Measure under realistic load — theoretical formulas are starting points, not answers
- **Thread Pool Isolation (Bulkhead)**: Use separate pools for different workload types — fast request handling, slow external API calls, background jobs. Prevents a slow operation from consuming all threads and starving fast operations. See Bulkhead Pattern
- **Java `ExecutorService`**: `Executors.newFixedThreadPool(n)`, `ThreadPoolExecutor` for fine-grained control. `ForkJoinPool` for divide-and-conquer work stealing. `CompletableFuture` submits to `ForkJoinPool.commonPool()` by default — avoid for blocking tasks
- **Python**: `concurrent.futures.ThreadPoolExecutor` for I/O-bound, `ProcessPoolExecutor` for CPU-bound (bypasses the GIL). Use as context managers for clean shutdown
- **Virtual Threads (Java 21+)**: Lightweight JVM-managed threads — millions can exist concurrently without the overhead of OS threads. Reduces the need for explicit async/reactive patterns for I/O-bound Java services
- **Monitoring**: Track queue depth, active thread count, rejection count, and task latency. Queue depth growth signals the pool is undersized for the load

## In Practice
Method Java services use `ThreadPoolExecutor` with bounded queues and explicit rejection policies. Pool sizes are configured per workload type with separate pools for request handling and background tasks. Python services use `ThreadPoolExecutor` for I/O-bound blocking calls from async contexts. Pool metrics are exported to Prometheus.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Thread Pools**: Always use bounded work queues — unbounded queues silently accumulate tasks until OOM kills your process. Use separate thread pools for different workload types (bulkhead) to prevent slow tasks from starving fast ones. Size CPU-bound pools at core count; size I/O-bound pools larger based on expected wait ratios. Monitor queue depth — a growing queue is an early warning that the pool is undersized. In Java 21+, consider virtual threads for I/O-bound work before reaching for explicit async patterns. → `engineering-knowledge-repository/thread-pools.md`

## Related Entries
- [Race Conditions](race-conditions.md) — thread pool workers sharing state require thread-safe data structures
- [Async Programming Patterns](async-programming-patterns.md) — thread pools execute blocking work offloaded from async event loops
- [Bulkhead Pattern](bulkhead-pattern.md) — separate thread pools per workload type implement the bulkhead pattern
- [Timeout Patterns](timeout-patterns.md) — tasks submitted to thread pools must respect timeouts to prevent unbounded queue buildup

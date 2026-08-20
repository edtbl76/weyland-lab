---
id: async-programming-patterns
tags: [pattern, concurrency, backend, frontend]
surfaces-at: [functional-design, code-generation]
related: [race-conditions, thread-pools, reactor-pattern, event-driven-architecture, actor-model]
complexity: intermediate
---

# Async Programming Patterns

## What It Is
Programming models that allow a single thread to handle multiple concurrent operations without blocking — instead of waiting idle for I/O to complete, the thread initiates the operation and resumes other work, returning to handle the result when it's ready. Async programming is the foundation of high-throughput I/O-bound systems: web servers, API clients, database access, file I/O. It enables massive concurrency (thousands of concurrent connections) with far fewer threads than blocking models.

## When to Apply
- I/O-bound workloads: network requests, database queries, file operations, external API calls
- High-concurrency servers that handle many simultaneous connections
- Frontend JavaScript — the entire browser runtime is single-threaded and async by necessity
- Anywhere that blocking threads on I/O would waste resources

## Key Concepts
- **Blocking vs. Non-Blocking I/O**: Blocking — thread waits idle until I/O completes (simple, wastes thread resources under load). Non-blocking — thread initiates I/O and is notified on completion; the thread is free to do other work while waiting
- **Callbacks**: The original async pattern — pass a function to be called when the operation completes. Leads to callback hell (deeply nested callbacks) for complex async flows. Superseded by promises/async-await in most contexts
- **Promises / Futures**: A value that will be available in the future. Composable — chain `.then()` for sequential async steps, `Promise.all()` for parallel. Avoids callback nesting
- **Async/Await**: Syntactic sugar over promises/futures — write async code that looks synchronous. `await` suspends the current coroutine until the awaited operation completes, yielding control to the event loop. Python `asyncio`, JavaScript `async/await`, Kotlin coroutines, C# `Task`
- **Event Loop**: The scheduler at the heart of async runtimes — runs coroutines, dispatches I/O completion events, manages timers. Single-threaded in Python asyncio and Node.js. Never block the event loop with CPU-intensive work — it starves all other coroutines
- **Coroutines**: Cooperative lightweight units of execution that yield control explicitly. Cheaper than threads — can run millions concurrently. Python `async def`, JavaScript `async function`, Kotlin `suspend fun`
- **CPU-Bound vs. I/O-Bound**: Async excels at I/O-bound work. For CPU-bound work, async provides no benefit — use process pools (Python `multiprocessing`) or worker threads. Mixing CPU-bound work into an async event loop blocks it
- **Async Context Propagation**: Correlation IDs, user context, and transaction context must be propagated explicitly in async code — thread-local storage doesn't work across coroutine switches. Python `contextvars`, Java Reactor's context
- **Structured Concurrency**: Running multiple async tasks with clear lifetime and cancellation semantics — all tasks complete or are cancelled before the parent scope exits. Python `asyncio.TaskGroup`, Java structured concurrency (JDK 21), Kotlin `coroutineScope`
- **Backpressure**: Async producers can outpace consumers — queues fill up, memory grows unbounded. Reactive streams (RxJava, Reactor, Python asyncio queues) provide backpressure mechanisms to signal the producer to slow down

## In Practice
Method Python services use `asyncio` with `httpx` for async HTTP clients and `asyncpg` for async database access. FastAPI and Starlette are the async web frameworks. CPU-bound tasks are offloaded to `ProcessPoolExecutor`. JavaScript/TypeScript services use `async/await` throughout. Correlation IDs are propagated via `contextvars`.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Async Programming**: Async is the right model for I/O-bound workloads — it enables high concurrency with few threads. Never block the event loop: no `time.sleep()`, no synchronous I/O, no CPU-intensive computation in async context — offload to a thread or process pool. Use structured concurrency (TaskGroup, coroutineScope) for managing groups of async tasks — it enforces clean cancellation and lifetime management. Propagate context explicitly with `contextvars`, not thread-locals. For backpressure, use bounded queues between producers and consumers — unbounded async queues lead to OOM under load. → `engineering-knowledge-repository/async-programming-patterns.md`

## Related Entries
- [Race Conditions](race-conditions.md) — async code has its own concurrency hazards when sharing state across coroutines
- [Thread Pools](thread-pools.md) — CPU-bound work from async contexts is offloaded to thread or process pools
- [Reactor Pattern](reactor-pattern.md) — the reactor pattern is the event-loop mechanism underlying async I/O frameworks
- [Event-Driven Architecture](event-driven-architecture.md) — async programming and event-driven architecture share non-blocking, event-dispatch foundations
- [Actor Model](actor-model.md) — actors provide an alternative concurrency model to async/await for stateful concurrent systems

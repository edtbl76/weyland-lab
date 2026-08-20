---
id: reactor-pattern
tags: [pattern, concurrency, backend, network]
surfaces-at: [application-design, functional-design]
related: [async-programming-patterns, actor-model, event-driven-architecture, thread-pools]
complexity: advanced
---

# Reactor Pattern

## What It Is
A structural concurrency pattern for handling service requests that are delivered concurrently by one or more inputs. The reactor waits for events (I/O readiness, timers, signals) using an event demultiplexer (OS-level `select`, `epoll`, `kqueue`), then dispatches each event synchronously to the associated handler. It is the architectural foundation of high-performance single-threaded event loops — Node.js, Python asyncio, Redis, Nginx, and Netty all implement variants of the reactor pattern. It enables a single thread to manage thousands of concurrent I/O operations without blocking.

## When to Apply
- Understanding how async I/O frameworks (asyncio, Node.js, Netty) work internally
- Designing high-performance network servers that handle massive connection concurrency
- Building custom event-driven I/O infrastructure (network servers, protocol implementations)

## Key Concepts
- **Event Demultiplexer**: The OS-level mechanism for monitoring multiple I/O sources simultaneously — `epoll` (Linux), `kqueue` (macOS/BSD), `IOCP` (Windows). Blocks until one or more I/O sources are ready (data available to read, socket ready to write), then returns the set of ready events. Zero CPU cost while waiting
- **Event Loop**: The reactor's core loop: call the demultiplexer to wait for events → receive ready events → dispatch each event to its registered handler → repeat. Single-threaded — handlers must be non-blocking and fast, or they stall the loop
- **Handler (Event Handler)**: A callback registered for a specific event on a specific resource. Called synchronously by the reactor when the event fires. Must not block — blocking handlers delay all other events in the loop
- **Dispatcher**: Routes events to the correct handler. In frameworks, this is implicit — `asyncio` event loop, Node.js libuv
- **Single-Threaded Reactor**: One event loop thread handles all I/O and dispatches handlers. Simple — no synchronization needed. Limitation: one CPU core. Node.js is the canonical example
- **Multi-Reactor (Boss-Worker)**: One reactor (boss) accepts connections; worker reactors (one per CPU core) handle established connections. Netty's default configuration. Scales across CPU cores
- **Proactor Pattern**: A variant where the OS completes the I/O operation and notifies the handler with the result (not just readiness). Windows IOCP and io_uring (Linux) implement proactor semantics. Higher performance for write-heavy workloads
- **Reactor vs. Thread-Per-Connection**: Thread-per-connection (traditional servlet model) — simple but doesn't scale past thousands of connections. Reactor — complex but handles hundreds of thousands of concurrent connections with a single thread
- **Non-Blocking Requirement**: The entire reactor pattern depends on handlers completing quickly and never blocking. A single blocking handler (synchronous database call, `time.sleep`) stalls all other events. Blocking I/O must be offloaded to a thread pool

## In Practice
Method uses asyncio (Python) and Node.js — both implement single-threaded reactor loops. Netty is used for high-performance Java network services. The reactor pattern is implicit in the frameworks; engineers interact with it through async/await abstractions. Understanding the reactor helps diagnose event loop stalls caused by accidentally blocking operations.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Reactor Pattern**: The reactor pattern is why a single thread can handle thousands of concurrent connections — it uses OS-level `epoll`/`kqueue` to wait for I/O readiness events instead of blocking threads. The critical constraint: handlers must never block — one blocking call stalls the entire event loop. This is why `await` exists in asyncio and Node.js — it yields back to the event loop rather than blocking the thread. Understanding the reactor helps you diagnose event loop lag: add latency monitoring on the event loop tick; spikes reveal inadvertently blocking operations. For CPU-bound work, offload to a thread pool — the reactor handles I/O, not computation. → `engineering-knowledge-repository/reactor-pattern.md`

## Related Entries
- [Async Programming Patterns](async-programming-patterns.md) — async/await is the developer-facing abstraction built on top of the reactor pattern
- [Actor Model](actor-model.md) — actors handle stateful concurrent computation; the reactor handles I/O event dispatch
- [Event-Driven Architecture](event-driven-architecture.md) — event-driven systems use reactor-pattern event loops for high-throughput event processing
- [Thread Pools](thread-pools.md) — blocking work is offloaded from the reactor event loop to thread pools

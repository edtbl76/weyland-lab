---
id: backpressure
tags: [pattern, concurrency, reliability, backend]
surfaces-at: [nfr-requirements, functional-design]
related: [producer-consumer-pattern, async-programming-patterns, stream-processing, api-rate-limiting-design, thread-pools]
complexity: intermediate
---

# Backpressure

## What It Is
A flow control mechanism where a slow consumer signals an upstream producer to slow down, preventing the producer from overwhelming the consumer with more work than it can process. Without backpressure, fast producers fill unbounded buffers until memory is exhausted, or drop work silently. With backpressure, the system degrades gracefully under overload — producers slow to match consumer capacity, queues stay bounded, and the system remains stable. Backpressure is a fundamental reliability property of well-designed concurrent and streaming systems.

## When to Apply
- Any producer-consumer pipeline where producers can outpace consumers
- Stream processing pipelines (Kafka consumers, reactive streams)
- Async I/O pipelines where data ingestion outpaces processing
- API gateways and load balancers under overload

## Key Concepts
- **Blocking Backpressure**: The producer blocks when the buffer is full — it cannot enqueue until a consumer frees space. Simple and safe; requires producers to be blockable (not event-loop threads). Java `ArrayBlockingQueue.put()`, Go channel sends on a full buffered channel
- **Rejection / Error Backpressure**: When the buffer is full, the producer receives an error or exception and is responsible for backing off. Used when blocking the producer is not acceptable (e.g., non-blocking event loops). The producer must handle the rejection gracefully — retry with backoff, drop, or propagate the signal upstream
- **Reactive Streams**: A specification (`java.util.concurrent.Flow`, RxJava, Project Reactor, Akka Streams) that formalizes backpressure in async pipelines. Subscribers request N items; publishers send at most N — demand-driven flow. The standard for JVM reactive programming
- **TCP Backpressure**: TCP's receive window is built-in backpressure — a slow receiver shrinks its window, signaling the sender to slow down. Application-level backpressure should mirror this model
- **Kafka Consumer Backpressure**: Kafka consumers pull messages at their own rate — inherent backpressure. If consumers fall behind, lag grows (visible in consumer group lag metrics). Backpressure is applied by simply not polling faster than you can process
- **Consequences of Missing Backpressure**:
  - *Memory exhaustion*: Unbounded queues fill until OOM
  - *Increased latency*: Large queues mean long wait times before processing
  - *Cascading failure*: A slow downstream causes upstream queues to fill, propagating the slowdown through the entire system
- **Shedding vs. Backpressure**: Load shedding (dropping requests under overload) is an alternative when propagating backpressure upstream is not feasible — e.g., at the edge where the client is external. Prefer backpressure for internal pipelines; load shedding at system boundaries

## In Practice
Method uses bounded `ArrayBlockingQueue` for in-process producer-consumer pipelines — blocking producers when full. Reactive pipelines use Project Reactor with explicit demand signaling. Kafka consumers are sized to maintain low consumer lag. API gateways apply rate limiting (a form of backpressure) at the entry point.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Backpressure**: Every producer-consumer pipeline needs backpressure — an unbounded queue between a fast producer and slow consumer is a slow OOM. Use bounded blocking queues for in-process pipelines. For async/reactive pipelines, use Reactive Streams (Project Reactor, RxJava) which have demand-driven backpressure built in. Monitor queue depth and consumer lag as leading indicators — they signal backpressure is building before failures occur. At system entry points where you can't propagate backpressure, use load shedding with clear error responses (429) rather than silently dropping work. → `engineering-knowledge-repository/backpressure.md`

## Related Entries
- [Producer-Consumer Pattern](producer-consumer-pattern.md) — backpressure is the flow control mechanism for producer-consumer pipelines
- [Async Programming Patterns](async-programming-patterns.md) — async pipelines require explicit backpressure to prevent event loop overload
- [Stream Processing](stream-processing.md) — stream processing frameworks provide built-in backpressure mechanisms
- [API Rate Limiting Design](api-rate-limiting-design.md) — rate limiting is backpressure applied at the API boundary
- [Thread Pools](thread-pools.md) — bounded thread pool queues implement backpressure on task submission

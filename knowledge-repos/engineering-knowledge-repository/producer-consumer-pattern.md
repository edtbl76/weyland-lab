---
id: producer-consumer-pattern
tags: [pattern, concurrency, backend]
surfaces-at: [functional-design, application-design]
related: [thread-pools, async-programming-patterns, message-queues, race-conditions, backpressure]
complexity: intermediate
---

# Producer-Consumer Pattern

## What It Is
A concurrency coordination pattern where one or more producer threads generate work items and place them in a shared buffer (queue), and one or more consumer threads retrieve and process those items. Producers and consumers operate at their own pace — the queue decouples production rate from consumption rate. This pattern is ubiquitous: web servers (request queue → worker threads), logging pipelines, stream processing, thread pools, and message broker architectures all implement it. Understanding it is foundational to understanding concurrent system design.

## When to Apply
- Decoupling work generation from work processing to allow independent scaling
- Smoothing out bursty production rates with a buffer before slower consumers
- Distributing work across multiple consumer threads
- Any pipeline where stages run at different speeds

## Key Concepts
- **Bounded Buffer**: A fixed-capacity queue between producers and consumers. When full, producers block or apply backpressure — prevents unbounded memory growth. Always use bounded buffers in production; unbounded queues are a silent OOM risk
- **Backpressure**: The signal from a full buffer to producers to slow down. Essential for stable systems — without it, fast producers overwhelm slow consumers and exhaust memory. Implementations: blocking put (producer waits), exception/rejection (producer backs off), reactive streams
- **Thread-Safe Queue**: The shared buffer must be thread-safe. Language-native implementations: Python `queue.Queue` (blocking, thread-safe), Java `LinkedBlockingQueue` / `ArrayBlockingQueue`, Go channels. Never use a non-thread-safe collection with manual locking when a native concurrent queue exists
- **Single vs. Multiple Producers/Consumers**: The pattern generalizes naturally — many producers can enqueue concurrently; many consumers can dequeue concurrently. The queue handles coordination
- **Work Stealing**: An optimization where idle consumers steal work from other consumers' local queues rather than waiting on a shared queue. Reduces contention and improves throughput for uneven workloads. Java's `ForkJoinPool` implements work stealing
- **Poison Pill Shutdown**: A sentinel value placed in the queue by producers to signal consumers to shut down gracefully. Each consumer, upon receiving the pill, may re-enqueue it for the next consumer before exiting
- **Queue Depth Monitoring**: Queue depth is the key operational metric — a growing queue signals consumer under-capacity. Alert and scale consumers when sustained queue depth exceeds a threshold
- **Relationship to Message Queues**: Message queues (SQS, Kafka) are the distributed, durable, infrastructure-level implementation of this pattern — producers and consumers may be different services on different machines. The conceptual model is identical

## In Practice
Method uses Python `queue.Queue` and Java `ArrayBlockingQueue` for in-process producer-consumer pipelines. Thread pools implement the consumer side. Queue depth is monitored as an operational health metric. Distributed producer-consumer workflows use SQS (bounded, durable, with DLQ) rather than in-process queues.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Producer-Consumer**: Always use a bounded queue — an unbounded queue between a fast producer and a slow consumer is a slow-motion OOM. Use language-native thread-safe queues (`queue.Queue`, `ArrayBlockingQueue`, Go channels) rather than a plain list with a lock. Monitor queue depth as a health signal — growth means consumers are falling behind. Use the poison pill pattern for clean shutdown. For cross-service producer-consumer workflows, use a message queue (SQS, Kafka) — same pattern, durable and distributed. → `engineering-knowledge-repository/producer-consumer-pattern.md`

## Related Entries
- [Thread Pools](thread-pools.md) — thread pools implement the consumer side of the producer-consumer pattern
- [Async Programming Patterns](async-programming-patterns.md) — async queues implement producer-consumer in event-loop contexts
- [Message Queues](message-queues.md) — the distributed, durable infrastructure-level form of the producer-consumer pattern
- [Race Conditions](race-conditions.md) — the shared buffer requires thread-safe access to prevent race conditions
- [Backpressure](backpressure.md) — backpressure is the mechanism by which a full consumer queue signals producers to slow down

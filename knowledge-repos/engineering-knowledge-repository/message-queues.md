---
id: message-queues
tags: [pattern, backend, distributed-systems, microservices]
surfaces-at: [application-design, functional-design]
related: [pub-sub, kafka, event-driven-architecture, asynchronous-processing, dead-letter-queue]
complexity: intermediate
---

# Message Queues

## What It Is
A form of asynchronous inter-service communication where producers place messages in a queue and consumers read from it independently. Message queues decouple the producer from the consumer in time — the producer doesn't wait for the consumer to process the message. This enables load leveling (queues absorb traffic spikes), resilience (messages persist if the consumer is temporarily unavailable), and loose coupling between services.

## When to Apply
- Decoupling services that don't need to communicate synchronously
- Load leveling — absorbing bursty traffic before slow downstream processing
- Work distribution — multiple workers consuming from the same queue
- Durable async operations — tasks that must complete even if a service restarts

## Key Concepts
- **Point-to-Point**: A message is consumed by one consumer. Standard queue semantics — each message is processed once (contrast with pub-sub fanout)
- **Durability**: Messages are persisted to disk — survive broker restarts and consumer failures. Critical for any work that must not be lost
- **Visibility Timeout**: After a consumer reads a message, it becomes invisible to other consumers for a timeout period. If processing completes successfully, the consumer deletes it. If not, the message reappears for another consumer — enables at-least-once delivery
- **Dead-Letter Queue (DLQ)**: A queue where messages that fail processing repeatedly are routed. Prevents a bad message from blocking the queue indefinitely. DLQ monitoring is essential — DLQ growth signals a processing bug
- **Message Ordering**: Standard queues don't guarantee ordering. FIFO queues (AWS SQS FIFO, RabbitMQ with single consumer) guarantee ordered delivery — at a throughput cost
- **Backpressure**: Queue depth signals producer rate vs. consumer capacity. Use queue depth as an autoscaling trigger — scale consumers when queue depth grows
- **At-Least-Once vs. Exactly-Once**: Most queues guarantee at-least-once delivery. Exactly-once requires either idempotent consumers (safe to process duplicates) or distributed transactions (expensive)
- **Common Implementations**: AWS SQS (managed, scalable, simple), RabbitMQ (feature-rich, self-hosted or managed), Azure Service Bus, Google Cloud Pub/Sub

## In Practice
Method uses AWS SQS for standard point-to-point work queues and SQS FIFO for ordered processing. DLQs are configured on all queues. Queue depth CloudWatch alarms trigger auto-scaling of consumer fleets. Consumers are designed to be idempotent given at-least-once delivery.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Message Queues**: Queues decouple producers and consumers in time — use them when services don't need synchronous responses. Always configure a dead-letter queue — a message that fails repeatedly will block your queue without one. Design consumers to be idempotent: at-least-once delivery means you'll occasionally process the same message twice. Use queue depth as your autoscaling signal, not CPU. For fan-out to multiple consumers, layer SNS on top of SQS rather than duplicating queues. → `engineering-knowledge-repository/message-queues.md`

## Related Entries
- [Pub-Sub](pub-sub.md) — pub-sub adds topic-based fanout routing on top of basic queue delivery
- [Kafka](kafka.md) — Kafka is a distributed log that extends message queue semantics with replay and high throughput
- [Event-Driven Architecture](event-driven-architecture.md) — message queues are the transport layer for event-driven architectures
- [Asynchronous Processing](asynchronous-processing.md) — message queues are the primary mechanism for async inter-service communication
- [Dead-Letter Queue](dead-letter-queue.md) — DLQs are a critical operational pattern for every queue deployment

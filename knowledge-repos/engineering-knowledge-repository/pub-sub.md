---
id: pub-sub
tags: [pattern, backend, distributed-systems, microservices]
surfaces-at: [application-design, functional-design]
related: [observer, event-driven-architecture, message-queues, kafka]
complexity: intermediate
---

# Publish-Subscribe Pattern

## What It Is
A messaging pattern where publishers send messages to named channels (topics) without knowledge of which subscribers will receive them, and subscribers express interest in topics without knowledge of which publishers produce them. Unlike direct point-to-point messaging, pub-sub fully decouples producers from consumers — neither knows the other exists. The message broker (Kafka, SNS, Redis Pub/Sub) is the intermediary that routes messages from publishers to all interested subscribers.

## When to Apply
- Fanout: one event needs to be delivered to multiple independent consumers
- Decoupling microservices — services react to events without direct dependencies
- Event-driven architectures where downstream processing is asynchronous
- Real-time notifications to multiple subscribers

## Key Concepts
- **Topic (Channel)**: A named channel through which messages flow. Publishers write to topics; subscribers read from topics. Topics define the logical separation of event streams
- **Publisher**: Sends messages to a topic. Has no knowledge of subscribers — fire and forget
- **Subscriber**: Registers interest in a topic. Receives all messages published to that topic after subscription
- **Broker**: The intermediary that receives published messages and routes them to all subscribers (Kafka, AWS SNS, Google Pub/Sub, Redis Pub/Sub, RabbitMQ exchanges)
- **Fan-out**: A single published message is delivered to all subscribers of a topic simultaneously. Useful for broadcasting events to multiple downstream services
- **Push vs. Pull Delivery**: Push — broker delivers to subscriber callbacks/webhooks (SNS). Pull — subscribers poll the broker for new messages (Kafka consumers). Pull enables replay and backpressure; push is simpler for low-volume cases
- **At-Least-Once vs. Exactly-Once**: Most pub-sub systems guarantee at-least-once delivery — subscribers must be idempotent. Exactly-once is harder and expensive; Kafka supports it with transactions
- **Topic Partitioning**: Kafka partitions topics for parallelism — messages with the same key go to the same partition, preserving ordering per key
- **Pub-Sub vs. Observer**: Observer is in-process (object references); pub-sub is distributed (network-level). The underlying pattern is the same; the implementation scale differs dramatically

## In Practice
Method uses AWS SNS for fan-out to multiple SQS queues (SNS+SQS pattern), Kafka for high-throughput event streams requiring replay and consumer groups, and Redis Pub/Sub for low-latency in-process signaling. Subscribers are designed to be idempotent given at-least-once delivery guarantees.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Pub-Sub**: Use pub-sub when one event must reach multiple independent consumers — don't create N direct calls. Publishers and subscribers should be fully decoupled through topics; neither should know the other exists. Design subscribers to be idempotent — at-least-once delivery is the standard guarantee. Use Kafka when you need replay, consumer groups, or high throughput. Use SNS+SQS for fanout with durable queuing and dead-letter queue support. → `engineering-knowledge-repository/pub-sub.md`

## Related Entries
- [Observer](observer.md) — pub-sub is the distributed, infrastructure-level form of the observer pattern
- [Event-Driven Architecture](event-driven-architecture.md) — pub-sub is a key mechanism in event-driven architectures
- [Message Queues](message-queues.md) — message queues provide reliable delivery; pub-sub adds fanout and topic routing on top
- [Kafka](kafka.md) — Kafka is the dominant distributed pub-sub platform for high-throughput event streams

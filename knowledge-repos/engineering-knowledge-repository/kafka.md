---
id: kafka
tags: [tooling, backend, distributed-systems, data]
surfaces-at: [application-design, infrastructure-design]
related: [pub-sub, message-queues, event-driven-architecture, stream-processing, data-pipelines]
complexity: intermediate
---

# Kafka

## What It Is
A distributed event streaming platform designed for high-throughput, fault-tolerant, persistent event streams. Unlike traditional message queues that delete messages after consumption, Kafka retains events in an ordered, immutable log for a configurable retention period — consumers can replay events, multiple independent consumer groups can read the same stream, and new consumers can catch up on historical events. Kafka is the de facto standard for high-throughput event streaming in distributed systems.

## When to Apply
- High-throughput event streams that exceed what traditional queues handle (millions of events/second)
- Multiple independent consumer groups need to process the same event stream
- Event replay is required — for recovery, reprocessing, or bootstrapping new consumers
- Building event sourcing or CQRS systems
- Real-time data pipelines and stream processing

## Key Concepts
- **Topic**: A named, append-only log. Producers write to topics; consumers read from topics. Messages are retained for a configurable period (time or size)
- **Partition**: Topics are divided into partitions — the unit of parallelism. Each partition is ordered. Messages with the same key always go to the same partition (key-based ordering guarantee). More partitions = more parallelism for consumers
- **Consumer Group**: A group of consumers that collectively consume a topic. Each partition is assigned to exactly one consumer in the group. Multiple consumer groups each get a full copy of the stream — independent processing
- **Offset**: A monotonically increasing integer identifying a message's position in a partition. Consumers track their current offset — decoupled from the broker's message retention. Enables replay by resetting the offset
- **Retention**: Kafka retains messages by time (e.g., 7 days) or size. Unlike queues, messages are not deleted on consumption. Enables reprocessing and consumer catch-up
- **Replication**: Each partition is replicated across multiple brokers. The leader handles writes; followers replicate. Provides fault tolerance — a broker failure doesn't lose data
- **Exactly-Once Semantics**: Kafka supports idempotent producers and transactional writes across partitions — enables exactly-once processing within Kafka. End-to-end exactly-once requires application-level idempotency
- **Kafka Streams / ksqlDB**: Stream processing frameworks built on Kafka — stateful aggregations, joins, and windowing directly on Kafka topics without a separate stream processor
- **Schema Registry**: Confluent Schema Registry enforces Avro/JSON Schema/Protobuf schemas on Kafka topics — prevents schema incompatibility between producers and consumers

## In Practice
Method uses Kafka (Confluent Cloud) for high-throughput event streams. Topics are partitioned by entity ID (user_id, order_id) for ordering guarantees. Schema Registry with Avro enforces schema compatibility. Consumer groups are used to run independent processing pipelines on the same event stream. Kafka Connect integrates with databases and S3 for change data capture and data lake ingestion.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Kafka**: Use Kafka when you need replay, multiple independent consumer groups, or throughput beyond what SQS/RabbitMQ handle. Partition by the entity key (user_id, order_id) to get ordering guarantees per entity without serializing all messages. Consumer groups give you independent processing pipelines — don't share consumer group IDs between unrelated processing. Enforce schemas with Schema Registry to prevent producer-consumer incompatibility. For simple point-to-point queuing without replay requirements, SQS is simpler and cheaper. → `engineering-knowledge-repository/kafka.md`

## Related Entries
- [Pub-Sub](pub-sub.md) — Kafka implements pub-sub semantics at high throughput with durable replay
- [Message Queues](message-queues.md) — traditional queues vs. Kafka's log-based approach
- [Event-Driven Architecture](event-driven-architecture.md) — Kafka is the dominant event bus for event-driven microservices
- [Stream Processing](stream-processing.md) — Kafka Streams and ksqlDB enable stream processing on Kafka topics
- [Data Pipelines](data-pipelines.md) — Kafka Connect and Kafka topics are foundational for data pipeline ingestion

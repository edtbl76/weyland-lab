---
id: stream-processing
tags: [pattern, backend, distributed-systems, data]
surfaces-at: [application-design, functional-design]
related: [kafka, data-pipelines, event-driven-architecture, batch-processing]
complexity: intermediate
---

# Stream Processing

## What It Is
Continuous computation on unbounded streams of data events as they arrive, rather than processing stored data in batches. Stream processing enables real-time analytics, alerting, aggregations, and transformations on live event streams. Unlike batch processing which runs periodically on accumulated data, stream processing operates with low latency — results are available seconds or milliseconds after events are produced.

## When to Apply
- Real-time analytics and dashboards (live user activity, operational metrics)
- Fraud detection and anomaly alerting that requires immediate action
- Real-time feature computation for ML models
- Event enrichment and transformation pipelines that feed downstream systems
- When batch processing latency (hours/minutes) is unacceptable

## Key Concepts
- **Unbounded Data**: Streams have no defined end — processing must handle data that arrives continuously and indefinitely
- **Windowing**: Grouping events into finite time windows for aggregation. Tumbling windows (non-overlapping fixed periods), sliding windows (overlapping), session windows (grouped by inactivity gaps)
- **Event Time vs. Processing Time**: Event time is when the event occurred; processing time is when it was processed. Events arrive out of order — use event time with watermarks to handle late-arriving data correctly
- **Watermarks**: Thresholds that declare "all events with event time < W have arrived" — enables correct windowing with out-of-order events at the cost of some latency
- **Stateful Processing**: Aggregations (counts, sums, averages) require state maintained across events. Stream processors manage state in fault-tolerant, distributed stores
- **Exactly-Once Processing**: Difficult in distributed systems — requires idempotent operations or distributed transactions. Most frameworks offer at-least-once by default
- **Apache Flink**: The leading open-source stream processing engine — low latency, true event-time processing, exactly-once semantics, stateful operators
- **Kafka Streams / ksqlDB**: Stream processing built directly on Kafka — lower operational overhead for Kafka-native pipelines. Good for moderate-complexity transformations
- **Apache Spark Structured Streaming**: Micro-batch processing with a streaming API — lower latency than batch Spark, higher latency than Flink. Good for teams already using Spark

## In Practice
Method uses Kafka Streams for lightweight streaming transformations in Kafka-native pipelines. Apache Flink is used for complex stateful aggregations and event-time windowing requirements. Real-time feature computation for ML serving uses Flink writing to a feature store.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Stream Processing**: Use event time, not processing time — out-of-order arrival is normal in distributed systems and event time with watermarks handles it correctly. Windowing is how you turn an infinite stream into finite aggregations — pick the window type that matches your use case (tumbling for period summaries, session for activity grouping). For Kafka-native pipelines, Kafka Streams is operationally simpler than deploying a separate Flink cluster. Exactly-once processing requires framework support AND idempotent sinks — it's not free. → `engineering-knowledge-repository/stream-processing.md`

## Related Entries
- [Kafka](kafka.md) — Kafka is the dominant event stream platform; Kafka Streams extends it with processing
- [Data Pipelines](data-pipelines.md) — stream processing is the real-time path in data pipeline architectures
- [Event-Driven Architecture](event-driven-architecture.md) — stream processing is the compute layer for event-driven data flows
- [Batch Processing](batch-processing.md) — batch processing is the alternative for non-real-time data workloads

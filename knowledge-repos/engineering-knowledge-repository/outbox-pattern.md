---
id: outbox-pattern
tags: [pattern, data, database, reliability, distributed-systems]
surfaces-at: [functional-design, nfr-design, infrastructure-design]
related: [saga-pattern, event-driven-architecture, microservices, cqrs]
complexity: intermediate
---

# Outbox Pattern

## What It Is
A pattern that guarantees reliable message publishing by writing events to an "outbox" table in the same database transaction as the business data change — then separately relaying those events to the message broker. This eliminates the dual-write problem: the risk that a service updates its database but crashes before publishing the event, or publishes the event but the database write fails.

## When to Apply
- Any service that must publish events or messages reliably after a state change
- Microservices systems where event loss would cause data inconsistency between services
- Saga implementations where each step must reliably trigger the next
- When "at-least-once delivery" is acceptable and consumers are idempotent

## When Not to Apply
- Single-service systems with no external event publishing
- When the message broker is the system of record — the outbox assumes a relational database as primary store
- Simple fire-and-forget notifications where occasional loss is acceptable

## Key Concepts
- **Dual-Write Problem**: Writing to a database AND publishing to a message broker in two separate operations — if either fails, state diverges
- **Outbox Table**: A table in the service's own database that stores pending events. Written atomically with the business transaction.
- **Message Relay**: A background process (polling or CDC-based) reads the outbox table and publishes events to the broker, then marks them as published
- **At-Least-Once Delivery**: The relay may publish the same event more than once (e.g., after a crash mid-relay) — consumers must be idempotent
- **Change Data Capture (CDC)**: An alternative relay mechanism — use the database's change log (e.g., Debezium with PostgreSQL WAL) to capture outbox writes and forward them to the broker. More efficient than polling.
- **Idempotency**: Downstream consumers must handle duplicate events gracefully

## In Practice
The Outbox Pattern is a standard reliability mechanism in Method microservices engagements wherever events are used for service coordination. It's the canonical solution to the dual-write problem and a prerequisite for reliable Saga implementations. The CDC-based relay (Debezium + Kafka) is the preferred implementation at scale; table polling is simpler for lower-throughput services. The pattern adds operational components (relay process or CDC pipeline) that must be accounted for in Infrastructure Design.

## Engineering Knowledge
💡 **Engineering Knowledge — Outbox Pattern**: Never write to your database and publish to a message broker as two separate steps — if you crash in between, you get inconsistency. Write the event to an outbox table in the same transaction as your data change; a relay process publishes it to the broker afterward. At-least-once delivery means your consumers must be idempotent. CDC-based relay (Debezium) is more efficient than polling at scale. → `engineering-knowledge-repository/infrastructure/outbox-pattern.md`

## Related Entries
- [Saga Pattern](saga-pattern.md) — the outbox pattern enables reliable saga step transitions
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — the outbox ensures reliable event publishing
- [Change Data Capture](../data/change-data-capture.md) — CDC is the preferred relay mechanism for outbox events

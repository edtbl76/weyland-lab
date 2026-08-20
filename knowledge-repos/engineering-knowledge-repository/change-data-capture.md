---
id: change-data-capture
tags: [pattern, data, database, distributed-systems]
surfaces-at: [nfr-design, infrastructure-design]
related: [outbox-pattern, event-sourcing, event-driven-architecture, data-mesh]
complexity: intermediate
---

# Change Data Capture (CDC)

## What It Is
A technique for tracking and capturing changes (inserts, updates, deletes) made to a database by reading the database's internal change log rather than modifying application code or adding triggers. CDC enables downstream systems to react to data changes in near real-time. The canonical open-source implementation is Debezium, which reads PostgreSQL WAL, MySQL binlog, and other database change logs, and streams change events to Kafka.

## When to Apply
- Synchronizing data between systems without tight coupling or dual writes
- Building event streams from legacy systems that can't be modified to publish events natively
- Implementing the Outbox Pattern relay — CDC reads the outbox table changes from the database log
- Data integration pipelines where replicating changes to downstream systems (data warehouse, search index, cache) is required
- Audit logging without application-level instrumentation

## When Not to Apply
- Simple single-database applications — CDC adds operational complexity without benefit
- When application-level event publishing is feasible and preferable — CDC at the database level is a lower-level abstraction
- Databases or managed services that don't expose change logs to external consumers
- When the change granularity needed doesn't align with row-level changes

## Key Concepts
- **Database Change Log**: Every major relational database maintains a log of all changes for recovery purposes — PostgreSQL WAL, MySQL binlog, SQL Server CDC, Oracle LogMiner
- **Debezium**: The dominant open-source CDC platform — reads database change logs and publishes change events to Kafka topics
- **Change Event**: A record capturing the before/after state of a row, the operation type (insert/update/delete), and metadata (timestamp, transaction ID)
- **Lag**: CDC introduces a small latency between the database write and the downstream event — typically milliseconds to seconds
- **Schema Registry**: Change events carry schema information — a schema registry (e.g., Confluent Schema Registry) manages compatibility as schemas evolve
- **Initial Snapshot**: CDC platforms can perform an initial full snapshot of existing data before streaming incremental changes

## In Practice
CDC appears in Method engagements primarily in two contexts: (1) as the relay mechanism for the Outbox Pattern, replacing polling with log-based event delivery, and (2) in data integration work where legacy systems must feed modern data platforms without refactoring. The Debezium + Kafka combination is the standard stack. CDC adds operational components (Debezium connector, Kafka cluster) that must be designed and operated — assess whether the integration need justifies the infrastructure investment.

## Engineering Knowledge
💡 **Engineering Knowledge — Change Data Capture**: Want to react to database changes without modifying the application? Read the database's own change log. CDC (Debezium + Kafka) turns every insert, update, and delete into a stream of events — no dual writes, no application instrumentation, no triggers. It's the preferred relay mechanism for the Outbox Pattern and a standard integration tool for feeding data to downstream systems. Adds operational infrastructure — worth it for integration-heavy architectures. → `engineering-knowledge-repository/data/change-data-capture.md`

## Related Entries
- [Outbox Pattern](../infrastructure/outbox-pattern.md) — CDC is the preferred relay mechanism for outbox events
- [Event Sourcing](event-sourcing.md) — CDC provides event-like streams from systems that don't natively source events
- [Data Mesh](data-mesh.md) — CDC enables domain data products to publish changes to the mesh
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — CDC is an event source for event-driven systems

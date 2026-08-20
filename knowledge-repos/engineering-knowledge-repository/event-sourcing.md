---
id: event-sourcing
tags: [pattern, backend, database, distributed-systems]
surfaces-at: [functional-design, nfr-requirements, application-design]
related: [cqrs, outbox-pattern, saga-pattern, event-driven-architecture]
complexity: advanced
---

# Event Sourcing

## What It Is
A persistence pattern where the state of a domain entity is derived entirely from a sequence of immutable domain events, rather than storing the current state directly. Instead of updating a row in a database, you append an event ("OrderPlaced", "ItemAdded", "OrderShipped") to an event log. The current state is reconstructed by replaying the event history. The event log is the source of truth.

## When to Apply
- Systems with strong audit trail requirements — the full history of every state change is inherent
- Complex domain models where understanding how state was reached matters as much as current state
- Systems requiring temporal queries — "what was the state of this entity on date X?"
- CQRS systems — event sourcing is a natural complement to CQRS's separated write/read models
- Financial systems, order management, and workflows where every transition must be traceable

## When Not to Apply
- Simple CRUD applications — event sourcing adds substantial complexity without benefit
- Systems where querying current state is the dominant use case and history is irrelevant
- Teams without experience managing event schema evolution — versioning immutable events is hard
- When the added operational complexity (event store, projection rebuilds) is not justified by the domain

## Key Concepts
- **Event**: An immutable record of something that happened — named in past tense ("OrderPlaced"), contains only the data relevant to that event
- **Event Store**: The append-only database of events — the system of record. Examples: EventStoreDB, Kafka (as event log), custom append-only table.
- **Aggregate**: The domain entity whose state is reconstructed by replaying its events
- **Projection**: A read model built by processing events — can be rebuilt at any time by replaying the event log
- **Snapshot**: A periodic checkpoint of aggregate state to avoid replaying the full history on every load — used when event history becomes long
- **Event Schema Evolution**: Events are immutable once written — versioning strategy (upcasting, versioned event types) must be designed upfront
- **Eventual Consistency**: Projections are updated asynchronously — reads may lag slightly behind writes

## In Practice
Event Sourcing appears in Method engagements in domains with inherent audit requirements — financial transactions, healthcare records, order management. It's almost always paired with CQRS: events are written by command handlers, projections serve queries. The operational overhead is real — event schema evolution, projection rebuilds, and snapshot management require dedicated engineering investment. Don't reach for event sourcing without a clear domain reason.

## Engineering Knowledge
💡 **Engineering Knowledge — Event Sourcing**: Instead of storing current state, store the sequence of events that produced it. You get a full audit log for free, temporal queries, and the ability to rebuild any read model from scratch. The cost: event schema versioning is hard, projections add eventual consistency, and operational complexity is significant. Pair with CQRS. Only apply when the domain genuinely benefits from the full event history — don't use it as a default persistence strategy. → `engineering-knowledge-repository/data/event-sourcing.md`

## Related Entries
- [CQRS](../architectural-styles/cqrs.md) — event sourcing and CQRS are natural companions
- [Outbox Pattern](../infrastructure/outbox-pattern.md) — the outbox publishes domain events reliably from the event store
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — events flow downstream to other services
- [Saga Pattern](../infrastructure/saga-pattern.md) — sagas can be implemented as event-sourced process managers

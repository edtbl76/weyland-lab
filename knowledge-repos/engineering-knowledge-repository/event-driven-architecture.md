---
id: event-driven-architecture
tags: [pattern, distributed-systems, backend]
surfaces-at: [application-design, nfr-design, infrastructure-design]
related: [cqrs, observer-pattern, circuit-breaker, domain-driven-design]
complexity: intermediate
---

# Event-Driven Architecture (EDA)

## What It Is
An architectural style where components communicate by producing and consuming events rather than calling each other directly. Producers emit events describing what happened. Consumers react to those events independently. Neither knows about the other — they share only the event contract.

## When to Apply
- Systems with multiple consumers of the same business event
- Workflows where steps can proceed asynchronously or in parallel
- Microservices that need to stay decoupled
- Systems with audit, replay, or temporal query requirements
- High-throughput scenarios where synchronous calls would create bottlenecks

## When Not to Apply
- Simple request/response flows where synchronous calls are sufficient
- Systems where strong consistency is required and eventual consistency is not acceptable
- Small teams or small systems where the operational overhead of a message broker is not justified
- When debugging and tracing complexity would overwhelm the team

## Key Concepts
- **Event**: An immutable record of something that happened — past tense, factual. "OrderPlaced", not "PlaceOrder".
- **Producer / Consumer**: Producers emit events; consumers subscribe and react. Decoupled by design.
- **Message Broker**: Infrastructure that routes events between producers and consumers (Kafka, SQS, EventBridge, RabbitMQ).
- **Event Sourcing**: Storing the full sequence of events as the system of record, rather than storing only current state. Enables replay and temporal queries. Higher complexity — not required for EDA.
- **Eventual Consistency**: In an event-driven system, consistency is achieved over time, not immediately. Design for this explicitly.

## In Practice
EDA decisions surface in Infrastructure Design (which broker, what topology) and NFR Design (resilience patterns, consumer failure handling). The observer-pattern is the code-level expression of the same principle. When designing Bounded Context integrations in DDD, Domain Events map naturally to an event-driven integration approach.

## Engineering Knowledge
💡 **Engineering Knowledge — Event-Driven Architecture**: If multiple components react to the same business occurrence, consider events instead of direct calls. Events decouple producers from consumers, enable async processing, and create a natural audit trail. Design your events as facts — past tense, immutable. → `engineering-knowledge-repository/architectural-styles/event-driven-architecture.md`

## Related Entries
- [CQRS](cqrs.md) — frequently paired with EDA for read/write separation
- [Observer Pattern](../design-patterns/observer-pattern.md) — the code-level expression of event-driven thinking
- [Circuit Breaker](../infrastructure/circuit-breaker.md) — essential resilience pattern for async consumer failures
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Domain Events are the DDD equivalent

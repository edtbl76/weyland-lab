---
id: cqrs
tags: [pattern, backend, database, distributed-systems]
surfaces-at: [application-design, functional-design]
related: [domain-driven-design, event-driven-architecture, repository-pattern]
complexity: intermediate
---

# CQRS — Command Query Responsibility Segregation

## What It Is
An architectural pattern that separates the model used to update data (Commands) from the model used to read data (Queries). Instead of one model doing both, you have two: one optimized for writes, one optimized for reads. This separation allows each side to evolve independently and be optimized for its specific purpose.

## When to Apply
- Systems with very different read and write workloads (e.g., write-heavy ingestion with read-heavy reporting)
- Complex domain models where queries are difficult because the write model is normalized for consistency
- Systems that benefit from separate scaling of read and write paths
- When paired with Event Sourcing to reconstruct state from events
- DDD-heavy systems where command handling and query handling have different complexity

## When Not to Apply
- Simple CRUD applications — CQRS adds significant complexity with no benefit
- Small teams without the capacity to maintain two models
- Systems where the read and write models are identical and unlikely to diverge
- Early-stage products where requirements are still being validated — add CQRS when you know you need it

## Key Concepts
- **Command**: An intent to change state — imperative, can be rejected. "PlaceOrder", "CancelBooking".
- **Query**: A request for data — no side effects, always succeeds (or returns empty). "GetOrderHistory".
- **Command Handler**: Processes a command, validates it, applies business rules, updates the write model.
- **Query Handler**: Reads from the read model — often a denormalized, query-optimized projection.
- **Read Model / Projection**: A denormalized view of the data built specifically for query needs — may be rebuilt from events.

## In Practice
CQRS surfaces naturally when teams find that their domain model is hard to query — the write model is normalized for consistency, but reporting needs denormalized views. It pairs well with DDD (commands map to Aggregate operations) and Event-Driven Architecture (events update read-model projections). Start simple — you can introduce CQRS incrementally when read/write complexity diverges.

## Engineering Knowledge
💡 **Engineering Knowledge — CQRS**: If your read and write concerns are pulling your model in different directions, consider separating them. Commands handle intent and business rules; queries handle data retrieval. You don't need both sides to be complex — even a simple read model can relieve significant pressure on a complex write model. → `engineering-knowledge-repository/architectural-styles/cqrs.md`

## Related Entries
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — commands map naturally to Aggregate operations
- [Event-Driven Architecture](event-driven-architecture.md) — events update CQRS read-model projections
- [Repository Pattern](../design-patterns/repository-pattern.md) — typically used for the write model in CQRS

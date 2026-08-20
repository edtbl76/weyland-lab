---
id: saga-pattern
tags: [pattern, distributed-systems, backend, reliability]
surfaces-at: [functional-design, nfr-design, infrastructure-design]
related: [microservices, event-driven-architecture, outbox-pattern, cqrs]
complexity: advanced
---

# Saga Pattern

## What It Is
A pattern for managing distributed transactions across multiple services without using a two-phase commit (2PC). A saga is a sequence of local transactions — each service performs its local transaction and publishes an event or message to trigger the next step. If a step fails, compensating transactions are executed to undo prior steps. There are two coordination styles: **Choreography** (services react to events, no central coordinator) and **Orchestration** (a central saga orchestrator issues commands to each service).

## When to Apply
- Multi-service business transactions that must maintain data consistency across service boundaries
- When 2PC is impractical due to service autonomy, technology heterogeneity, or availability requirements
- Long-running business processes that span minutes or hours
- Systems that can tolerate eventual consistency (as opposed to immediate consistency)

## When Not to Apply
- Single-service operations — no saga needed, use a local transaction
- When strong immediate consistency is required and cannot be relaxed — rethink the service boundary
- Small teams without experience managing distributed state — the operational complexity is significant
- When the number of steps is very small and choreography would be simpler than it looks

## Key Concepts
- **Local Transaction**: Each step in a saga is a local ACID transaction within one service
- **Compensating Transaction**: The undo operation for each step — must be explicitly designed for every step that can fail
- **Choreography**: Each service publishes events; downstream services react. Decentralized but harder to visualize.
- **Orchestration**: A central saga orchestrator (process manager) tells each service what to do. Easier to reason about; creates a coordination dependency.
- **Eventual Consistency**: Saga guarantees that either all steps complete or compensating transactions restore a consistent state — but intermediate states are visible during execution
- **Idempotency**: Each step and compensating transaction must be idempotent — they may be retried

## In Practice
Sagas emerge in Method engagements whenever a business transaction spans more than one service boundary — order placement across inventory, payment, and fulfillment services is the canonical example. Choreography-style sagas are simpler to start with; orchestration is easier to debug and monitor as complexity grows. The Outbox Pattern is a critical companion — it ensures events are published reliably alongside local transactions.

## Engineering Knowledge
💡 **Engineering Knowledge — Saga Pattern**: In microservices, you can't wrap multiple services in a single database transaction. Use a saga: a sequence of local transactions, each paired with a compensating transaction if something goes wrong. Choreography (event-driven, decentralized) is simpler to start; orchestration (central coordinator) is easier to trace. Either way, design your compensating transactions first — they're harder than the happy path. → `engineering-knowledge-repository/infrastructure/saga-pattern.md`

## Related Entries
- [Outbox Pattern](outbox-pattern.md) — reliable event publishing for saga steps
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — choreography-style sagas are event-driven
- [CQRS](../architectural-styles/cqrs.md) — often paired with sagas for command handling
- [Microservices](../architectural-styles/microservices.md) — the context in which sagas are needed

---
id: choreography-vs-orchestration
tags: [pattern, distributed-systems, backend]
surfaces-at: [application-design, functional-design, infrastructure-design]
related: [saga-pattern, event-driven-architecture, microservices, mediator]
complexity: intermediate
---

# Choreography vs. Orchestration

## What It Is
Two fundamental approaches to coordinating workflows across multiple services:

**Choreography**: Services react to events. Each service knows what to do when it hears a certain event and publishes its own events when done. No central coordinator — the workflow emerges from the services' collective behavior.

**Orchestration**: A central coordinator (orchestrator) explicitly tells each service what to do, in what order, and handles failures. The workflow is visible in one place.

## When to Apply
**Choreography**:
- Loose coupling is the priority — services should evolve independently
- Simple, fan-out style workflows where steps are largely independent
- Event-driven architectures where services already communicate via events
- When adding a new step should not require modifying a central component

**Orchestration**:
- Complex workflows with conditional branching, error handling, and compensation
- When workflow visibility and debuggability are important
- Long-running workflows that need durable state tracking
- When the overall business process needs to be visible and manageable from a central place

## When Not to Apply
- Neither is universally better — the choice depends on coupling tolerance, complexity, and operational visibility needs
- Don't use pure choreography for complex multi-step workflows where debugging "what state is this order in?" becomes a support burden

## Key Concepts
- **Choreography**: No central brain — services listen for events, act, and emit events. Decentralized. Harder to visualize and debug.
- **Orchestration**: A central saga orchestrator (process manager, workflow engine) issues commands and tracks state. Centralized. Easier to visualize; creates a coordination dependency.
- **Hybrid**: Most real systems use both — choreography for loose event reactions, orchestration for complex transactional workflows
- **Workflow Engines**: AWS Step Functions, Temporal, Conductor — orchestration platforms that provide durable state, retries, and visual workflow representation
- **Saga**: Distributed transactions use either choreography (event-based) or orchestration (process manager) to sequence and compensate

## In Practice
Method's default for simple, event-driven microservices coordination is choreography — it's easier to start with and scales well. For complex, multi-step business processes (order fulfillment, onboarding workflows, approval chains), orchestration with a workflow engine (Temporal, AWS Step Functions) provides the visibility and durability that choreography lacks. Debugging a choreographed workflow gone wrong requires tracing events across multiple services; an orchestrated workflow shows its state in one place.

## Engineering Knowledge
💡 **Engineering Knowledge — Choreography vs. Orchestration**: Choreography: services react to events — decentralized, loosely coupled, emergent flow. Orchestration: a central coordinator drives the workflow — explicit, debuggable, stateful. Use choreography for simple event-driven reactions; use orchestration (Temporal, AWS Step Functions) for complex multi-step workflows where you need to answer "what state is this order in?" from one place. Most real systems need both. → `engineering-knowledge-repository/architectural-styles/choreography-vs-orchestration.md`

## Related Entries
- [Saga Pattern](../infrastructure/saga-pattern.md) — sagas use either choreography or orchestration for distributed transactions
- [Event-Driven Architecture](event-driven-architecture.md) — choreography is a natural fit for event-driven systems
- [Mediator Pattern](../design-patterns/mediator.md) — an orchestrator is a mediator at architectural scale

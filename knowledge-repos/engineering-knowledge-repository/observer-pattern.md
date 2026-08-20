---
id: observer-pattern
tags: [pattern, backend]
surfaces-at: [nfr-design, code-generation]
related: [event-driven-architecture, strategy-pattern, domain-driven-design]
complexity: foundational
---

# Observer Pattern

## What It Is
A behavioral design pattern where an object (the Subject) maintains a list of dependents (Observers) and notifies them automatically when its state changes. Observers register interest; the Subject broadcasts changes without knowing who is listening. Part of the Gang of Four behavioral patterns.

## When to Apply
- When one object's state change should trigger updates in other objects without tight coupling
- Event handling systems — UI events, domain events, system notifications
- When the number of observers is unknown at design time or varies at runtime
- Implementing event buses or pub/sub within a single service

## When Not to Apply
- When observers need to respond synchronously and in a guaranteed order — the pattern does not guarantee order
- When the notification chain is complex enough to create debugging nightmares (cascading notifications)
- Distributed systems — use a message broker instead of in-process observer for cross-service events

## Key Concepts
- **Subject (Observable)**: Maintains the list of observers and notifies them on state change
- **Observer**: Implements an interface with an `update` or `notify` method
- **Loose coupling**: Subjects don't know the concrete type of their observers — just the interface
- **Push vs Pull**: The Subject can push data to observers (send the changed data) or observers can pull (query the subject after notification)

## In Practice
Observer is the code-level expression of event-driven thinking within a single service. Domain Events in DDD are often implemented via an Observer mechanism internally. In Code Generation, event handlers and listeners follow the Observer structure. At the infrastructure level, EDA with a message broker replaces Observer for cross-service communication.

## Engineering Knowledge
💡 **Engineering Knowledge — Observer Pattern**: When one state change needs to trigger reactions in multiple other components, use Observer instead of direct calls. It decouples the thing that changed from the things that care — adding or removing reactions requires no changes to the Subject. → `engineering-knowledge-repository/design-patterns/observer-pattern.md`

## Related Entries
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — the architectural-scale equivalent
- [Strategy Pattern](strategy-pattern.md) — often used together with Observer for pluggable behavior

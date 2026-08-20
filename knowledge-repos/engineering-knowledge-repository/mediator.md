---
id: mediator
tags: [pattern, backend]
surfaces-at: [functional-design, application-design, code-generation]
related: [observer-pattern, command-pattern, facade-pattern, event-driven-architecture]
complexity: intermediate
---

# Mediator Pattern

## What It Is
A behavioral pattern that defines an object (the mediator) that encapsulates how a set of objects interact. Instead of objects communicating directly with each other (creating a tightly-coupled web of dependencies), they communicate through the mediator. This centralizes coordination logic and reduces the coupling between communicating objects.

## When to Apply
- A set of objects communicate in complex but well-defined ways — the interdependencies are tangled
- Reusing an object is difficult because it refers to and communicates with many others
- Behavior distributed among multiple classes should be customizable without subclassing
- UI form logic: when one control changes, multiple other controls must update — coordinate through a mediator

## When Not to Apply
- When the mediator itself becomes a "God Object" — if it accumulates too much logic, the pattern has been misapplied
- Simple communication patterns where direct references are clear and maintainable
- When an existing event bus or message broker already handles the coordination need

## Key Concepts
- **Mediator Interface**: Defines the communication interface that colleagues use to notify the mediator of events
- **Concrete Mediator**: Implements coordination logic — knows about and coordinates colleague objects
- **Colleague**: An object that communicates with others exclusively through the mediator
- **Reduced Coupling**: Colleagues go from M×N dependencies to M+N — each knows only the mediator, not each other
- **Event Bus as Mediator**: In-process event buses (MediatR in .NET, Spring ApplicationEventPublisher) are mediator implementations — components publish events; the mediator routes to handlers

## In Practice
MediatR is the canonical Mediator implementation in .NET applications — it implements CQRS dispatch (command → handler, query → handler) as a mediator. In frontend frameworks, Redux's store and React Context act as mediators. In Method engagements, the Mediator pattern is the mechanism behind CQRS command/query dispatch and is frequently used to decouple domain events from their handlers inside a service.

## Engineering Knowledge
💡 **Engineering Knowledge — Mediator Pattern**: When many objects need to coordinate but direct wiring creates a coupling spider web, introduce a mediator as the central coordinator. Objects publish to the mediator; it routes to the right receiver. MediatR (.NET) is the most common implementation — it's how CQRS command dispatch works. The risk: the mediator becomes a God Object if coordination logic grows unchecked. → `engineering-knowledge-repository/design-patterns/mediator.md`

## Related Entries
- [Observer Pattern](observer-pattern.md) — Observer is one-to-many notification; Mediator is many-to-many coordination through a central hub
- [Command Pattern](command-pattern.md) — Mediators often dispatch Command objects to their handlers
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — an event bus is a distributed Mediator
- [Facade Pattern](facade-pattern.md) — Facade simplifies access to a subsystem; Mediator coordinates between peers

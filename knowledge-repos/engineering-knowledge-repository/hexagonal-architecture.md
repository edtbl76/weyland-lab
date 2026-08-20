---
id: hexagonal-architecture
tags: [pattern, backend]
surfaces-at: [application-design, functional-design]
related: [clean-architecture, domain-driven-design, adapter-pattern, dependency-injection, solid-principles]
complexity: intermediate
---

# Hexagonal Architecture (Ports and Adapters)

## What It Is
An architectural style that isolates the application's core domain from external concerns — databases, UIs, message queues, external APIs — using a ports and adapters model. The domain is at the center; all external systems connect to it through defined ports (interfaces). Adapters implement those ports for specific technologies. Coined by Alistair Cockburn. Sometimes called "Ports and Adapters."

## When to Apply
- Systems where testability of business logic is a priority
- When the external systems (databases, APIs, UIs) are likely to change
- Long-lived systems where the domain must remain stable as technology evolves
- DDD-based systems — Hexagonal Architecture is a natural fit for protecting the domain model

## When Not to Apply
- Simple CRUD applications with minimal domain logic — the structural overhead isn't justified
- Short-lived projects where the investment in clean separation won't pay back
- Teams unfamiliar with the pattern without time to learn — a poorly applied Hexagonal architecture is worse than a layered one done well

## Key Concepts
- **Domain Core**: The center — pure business logic, no framework or technology dependencies
- **Port**: An interface defined by the domain that expresses what it needs (driven port) or what it provides (driving port)
- **Adapter**: An implementation of a port for a specific technology (a Repository that talks to Postgres, a Controller that handles HTTP)
- **Driving Side (Primary)**: Adapters that call the domain — UI, REST controllers, CLI, test harnesses
- **Driven Side (Secondary)**: Adapters that the domain calls — databases, message queues, external APIs
- **Dependency Rule**: Dependencies always point inward — adapters depend on the domain, never the reverse

## In Practice
Hexagonal Architecture produces systems that are trivially testable — the domain core has no framework dependencies and can be tested with pure unit tests. The driving adapter for production is an HTTP controller; the driving adapter for tests is a test harness that calls the domain directly. In Code Generation, the project structure reflects the hexagon: `domain/`, `application/`, `adapters/` or `infrastructure/`.

## Engineering Knowledge
💡 **Engineering Knowledge — Hexagonal Architecture**: Protect your domain from technology. Define Ports (interfaces) that express what the domain needs — Adapters implement those ports for specific technologies. The domain never imports a framework. This makes the core testable in isolation and the technology swappable without touching business logic. → `engineering-knowledge-repository/architectural-philosophy/hexagonal-architecture.md`

## Related Entries
- [Clean Architecture](clean-architecture.md) — related architectural philosophy with the same dependency rule
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Hexagonal Architecture is the structural complement to DDD
- [Adapter Pattern](../design-patterns/adapter-pattern.md) — adapters implement the ports
- [Dependency Injection](../design-patterns/dependency-injection.md) — wires adapters to ports at startup

---
id: clean-architecture
tags: [pattern, backend]
surfaces-at: [application-design, functional-design]
related: [hexagonal-architecture, solid-principles, domain-driven-design, dependency-injection]
complexity: intermediate
---

# Clean Architecture

## What It Is
An architectural philosophy by Robert C. Martin (Uncle Bob) that organizes code into concentric layers — Entities, Use Cases, Interface Adapters, and Frameworks/Drivers. The Dependency Rule is absolute: source code dependencies can only point inward. Nothing in an inner circle can know anything about an outer circle. The result: business rules are independent of frameworks, UI, and databases.

## When to Apply
- Systems where business rules must remain stable across technology changes
- Long-lived applications where testability and maintainability are first-class concerns
- When you want to defer framework and database decisions — or change them later
- Teams that want a clear, opinionated structure for separating concerns

## When Not to Apply
- Simple applications where the overhead of strict layering produces more ceremony than value
- Short-lived projects or prototypes
- Teams without experience in the pattern — misapplied Clean Architecture is more painful than a well-organized layered architecture

## Key Concepts
- **Entities**: Core business objects with the highest-level rules — no framework dependencies
- **Use Cases (Interactors)**: Application-specific business rules — orchestrate Entities to fulfill user intentions
- **Interface Adapters**: Convert data between the format most convenient for Use Cases and the format required by external agencies (controllers, presenters, gateways)
- **Frameworks and Drivers**: Outermost layer — databases, web frameworks, UI. Treated as details that can be swapped
- **The Dependency Rule**: Dependencies point inward only. Inner circles define interfaces; outer circles implement them.
- **Screaming Architecture**: The top-level directory structure should scream the domain — not the framework. `Billing/`, `Orders/`, not `Controllers/`, `Models/`

## In Practice
Clean Architecture and Hexagonal Architecture share the same core dependency rule — they are complementary philosophies, not competing ones. Clean Architecture is more prescriptive about layers; Hexagonal is more prescriptive about ports and adapters. In practice, many teams blend them. The actionable takeaway for most projects: keep business rules in one place with no framework imports; let everything else depend on that core.

## Engineering Knowledge
💡 **Engineering Knowledge — Clean Architecture**: The dependency rule is the insight: source code dependencies point inward. Business rules at the center, frameworks at the edge. Your Use Cases shouldn't import Spring, Rails, or React — those are details. When your framework changes, the business logic doesn't. → `engineering-knowledge-repository/architectural-philosophy/clean-architecture.md`

## Related Entries
- [Hexagonal Architecture](hexagonal-architecture.md) — complementary philosophy with the same dependency rule
- [SOLID Principles](solid-principles.md) — Clean Architecture is SOLID applied at the architectural scale
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Entities in Clean Architecture align with DDD Aggregates

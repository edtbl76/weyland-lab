---
id: separation-of-concerns
tags: [principle, backend]
surfaces-at: [application-design, functional-design, code-generation]
related: [solid-principles, dry-principle, hexagonal-architecture, clean-architecture, layered-architecture]
complexity: foundational
---

# Separation of Concerns (SoC)

## What It Is
The principle of organizing software so that each section addresses a distinct concern — a distinct set of information or responsibility. A "concern" is any aspect that affects the behavior of the code. By separating concerns, each piece of code can be reasoned about, modified, and tested in isolation. Coined by Edsger Dijkstra in 1974.

## When to Apply
- When designing module and layer boundaries — each layer/module should own one concern
- When reviewing code that has multiple reasons to change — split it along concern lines
- When writing functions or classes that are doing too much — "too much" often means "multiple concerns"
- When designing APIs — separate the API concern from the implementation concern

## When Not to Apply
- Taken to extremes, over-separation creates excessive indirection and boilerplate. Not every aspect of behavior warrants its own module.
- Simple scripts and utilities where strict layering adds overhead without benefit
- When concerns are genuinely inextricable — don't force artificial separation

## Key Concepts
- **Concern**: A distinct piece of functionality, behavior, or information — business logic, data access, presentation, logging, authentication
- **Cohesion**: Code that addresses the same concern belongs together — high cohesion is the goal
- **Coupling**: Code that addresses different concerns should have minimal dependencies — low coupling is the goal
- **Layered Architecture**: The most common SoC pattern — presentation, application, domain, infrastructure layers each own their concern
- **Cross-Cutting Concerns**: Concerns that appear throughout the system (logging, security, caching) — addressed via AOP, middleware, or decorator patterns rather than scattered inline code
- **Single Responsibility Principle**: SRP is SoC applied at the class level — each class should have one reason to change

## In Practice
SoC is the foundation behind every architectural layering decision in Method engagements — hexagonal architecture, clean architecture, and layered architecture all operationalize SoC at the structural level. The most common violation is business logic leaking into presentation layers or data access code. The test: can you change one concern (e.g., switch from REST to GraphQL, or swap the database) without touching the other? If not, the concerns are not separated.

## Engineering Knowledge
💡 **Engineering Knowledge — Separation of Concerns**: Each module, layer, or class should own one distinct concern — and changes to that concern should be contained within it. The test: can you change the database without touching business logic? Can you add an endpoint without rewriting validation? If not, concerns are mixed. SoC is the principle behind every layering decision — hexagonal, clean, and layered architectures are all SoC applied at architectural scale. → `engineering-knowledge-repository/architectural-philosophy/separation-of-concerns.md`

## Related Entries
- [SOLID Principles](solid-principles.md) — Single Responsibility Principle is SoC at the class level
- [Hexagonal Architecture](hexagonal-architecture.md) — operationalizes SoC between domain and infrastructure
- [Clean Architecture](clean-architecture.md) — operationalizes SoC across all architectural rings
- [Layered Architecture](../architectural-styles/layered-architecture.md) — the most common SoC pattern in enterprise software

---
id: layered-architecture
tags: [pattern, backend]
surfaces-at: [application-design, functional-design]
related: [hexagonal-architecture, clean-architecture, separation-of-concerns, modular-monolith]
complexity: foundational
---

# Layered Architecture

## What It Is
An architectural style that organizes code into horizontal layers, each with a specific role. The most common form is four layers: **Presentation** (handles input/output), **Application** (orchestrates use cases), **Domain** (business logic), and **Infrastructure** (databases, external APIs). Each layer depends only on the layer below it — not on layers above. The most widely-used enterprise application architecture.

## When to Apply
- Most enterprise and web applications — layered architecture is the sensible default
- When the team is familiar with layered patterns and the system doesn't have unusual requirements
- CRUD-heavy applications where the domain logic is moderate and the separation of UI, business, and data concerns is the primary need
- As the starting structure before more sophisticated architectures are justified

## When Not to Apply
- When domain logic is complex and the layered model causes domain objects to be anemic (see Hexagonal or Clean Architecture instead)
- When the infrastructure layer must be swappable from the domain perspective — layered architecture creates upward infrastructure dependencies that Hexagonal Architecture explicitly inverts
- When the application has radically different concerns that don't map to horizontal layers

## Key Concepts
- **Strict Layering**: Each layer can only call the layer directly beneath it — skipping layers is not allowed
- **Relaxed Layering**: Lower layers can be accessed by any layer above — more pragmatic, more common in practice
- **Presentation Layer**: UI, REST controllers, GraphQL resolvers — receives input and sends output; no business logic
- **Application Layer**: Orchestrates use cases, coordinates domain objects and services; thin
- **Domain Layer**: Business logic, entities, value objects, domain services; has no knowledge of infrastructure
- **Infrastructure Layer**: Database, messaging, external API clients; implements interfaces defined by higher layers
- **Dependency Direction**: Always points downward — higher layers depend on lower ones, not the reverse
- **Layer Bypass**: A common violation — controllers accessing data access objects directly, bypassing the domain. Breaks separation.

## In Practice
Layered architecture is the entry point for most Method engineering engagements. The discipline is enforcing layer boundaries: no business logic in controllers, no database access in domain classes, no domain imports in the presentation layer. When domain logic becomes rich enough to need protection from infrastructure concerns, evolve toward Hexagonal or Clean Architecture.

## Engineering Knowledge
💡 **Engineering Knowledge — Layered Architecture**: The sensible default for most applications: Presentation → Application → Domain → Infrastructure. Each layer depends only on what's below it; business logic lives in the domain layer, not in controllers or database classes. The most common violation: controllers that bypass the domain and talk directly to the database. When your domain logic gets rich and infrastructure starts leaking in, that's the signal to evolve toward Hexagonal Architecture. → `engineering-knowledge-repository/architectural-styles/layered-architecture.md`

## Related Entries
- [Hexagonal Architecture](../architectural-philosophy/hexagonal-architecture.md) — the evolution when layered architecture allows infrastructure to pollute the domain
- [Clean Architecture](../architectural-philosophy/clean-architecture.md) — Clean Architecture generalizes layered patterns with explicit dependency rules
- [Separation of Concerns](../architectural-philosophy/separation-of-concerns.md) — layered architecture is SoC applied at system scale

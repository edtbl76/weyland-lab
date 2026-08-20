---
id: modular-monolith
tags: [pattern, backend, monolith]
surfaces-at: [application-design, nfr-requirements]
related: [microservices, domain-driven-design, hexagonal-architecture, strangler-fig]
complexity: foundational
---

# Modular Monolith

## What It Is
A single deployable unit structured with strong internal module boundaries — each module owns its domain, exposes a defined interface, and enforces that other modules cannot reach into its internals. The deployment is a monolith; the architecture is modular. Sometimes called a "majestic monolith" or "well-structured monolith."

## When to Apply
- Greenfield projects where service boundaries are not yet fully understood
- Small to medium teams that don't need independent deployability
- Systems where the distributed systems tax of microservices is not justified
- As the starting architecture when microservices may be introduced later — modules become services

## When Not to Apply
- When multiple teams genuinely need to deploy independently and are blocked by a shared codebase
- When parts of the system have radically different scaling requirements that can't be addressed within a monolith
- When the codebase is already a "big ball of mud" — a modular monolith requires disciplined enforcement of boundaries

## Key Concepts
- **Module Boundary**: Each module has a public API and hides its internals — other modules call the API, never internal classes
- **No Shared Database Tables Across Modules**: Each module owns its data schema, even within a shared database
- **Enforced Boundaries**: Module boundaries are enforced by code structure, package visibility, architecture tests (ArchUnit, NetArchTest), or linting rules — not by convention alone
- **Path to Microservices**: A well-structured modular monolith can be decomposed into microservices later — each module becomes a service. This is dramatically easier than decomposing a big ball of mud.

## In Practice
Method's default starting point for most greenfield systems. The discipline of module boundaries delivers most of the organizational benefits of microservices without the operational complexity. When a module needs to scale independently, it can be extracted as a service — the interface already exists. In Application Design, modules map to DDD Bounded Contexts.

## Engineering Knowledge
💡 **Engineering Knowledge — Modular Monolith**: Start here, not with microservices. Strong module boundaries in a single codebase give you 80% of the architectural benefit with 20% of the complexity. When you genuinely need independent deployability, extract modules as services — the boundaries are already defined. Don't pay the distributed systems tax before you need to. → `engineering-knowledge-repository/architectural-styles/modular-monolith.md`

## Related Entries
- [Microservices](microservices.md) — where a modular monolith evolves when independent deployability is needed
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Bounded Contexts define module boundaries
- [Strangler Fig](../infrastructure/strangler-fig.md) — how to extract modules from a monolith incrementally

---
id: domain-driven-design
tags: [methodology, backend]
surfaces-at: [application-design, functional-design, requirements-analysis]
related: [cqrs, event-driven-architecture, repository-pattern, strategy-pattern]
complexity: foundational
---

# Domain-Driven Design (DDD)

## What It Is
A software design approach that centers the model on the business domain rather than technical concerns. DDD aligns the code structure, language, and boundaries with how the business actually works — making the software a direct reflection of domain knowledge.

## When to Apply
- Complex business logic with rich rules, workflows, or domain concepts
- Multiple teams working on the same system (boundaries prevent coupling)
- When the business domain is the primary source of complexity (not technical infrastructure)
- Long-lived systems where the domain will evolve

## When Not to Apply
- Simple CRUD applications with no meaningful business logic
- Short-lived tools or throwaway scripts
- Systems where data transformation is the primary concern (ETL, reporting pipelines)
- When the team does not have access to domain experts

## Key Concepts
- **Ubiquitous Language**: A shared vocabulary between engineers and business stakeholders — used consistently in code, docs, and conversation. Eliminates translation errors.
- **Bounded Context**: An explicit boundary within which a model applies. Different contexts can use the same word to mean different things — and that's okay, as long as boundaries are clear.
- **Aggregate**: A cluster of domain objects treated as a single unit for data changes. One object is the Aggregate Root — all external references go through it.
- **Entity vs Value Object**: Entities have identity that persists over time. Value Objects are defined entirely by their attributes — two Value Objects with the same data are identical.
- **Domain Events**: Something meaningful that happened in the domain — past tense, immutable. Used to communicate across Bounded Contexts.

## In Practice
DDD surfaces most directly during Functional Design (designing Aggregates, Entities, and business rules) and Application Design (defining Bounded Contexts and service boundaries). When teams are naming things differently in different meetings, that's a signal to establish Ubiquitous Language. When services are getting tangled, that's a signal to revisit Bounded Context boundaries.

## Engineering Knowledge
💡 **Engineering Knowledge — Domain-Driven Design**: You're designing a domain model. Before defining entities, establish your Bounded Contexts — the explicit boundaries within which your model is consistent. Entities that cross context boundaries are a leading cause of coupling. → `engineering-knowledge-repository/methodologies/domain-driven-design.md`

## Related Entries
- [CQRS](../architectural-styles/cqrs.md) — often paired with DDD for read/write separation
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — Domain Events are a natural fit for event-driven systems
- [Repository Pattern](../design-patterns/repository-pattern.md) — the standard DDD pattern for data access
- [Strategy Pattern](../design-patterns/strategy-pattern.md) — useful for encapsulating business rules that vary

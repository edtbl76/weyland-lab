---
id: repository-pattern
tags: [pattern, backend, database]
surfaces-at: [functional-design, application-design, code-generation]
related: [domain-driven-design, cqrs, factory-pattern]
complexity: foundational
---

# Repository Pattern

## What It Is
A design pattern that abstracts the data access layer behind a collection-like interface. Business logic works with a Repository as if domain objects are stored in an in-memory collection — it has no knowledge of the underlying persistence mechanism (database, API, cache). The Repository handles the translation.

## When to Apply
- Any application with a persistence layer and non-trivial business logic
- When you want to unit test business logic without a real database
- DDD-based systems (Repository is the standard DDD data access pattern)
- When the persistence mechanism might change or is abstracted behind a service

## When Not to Apply
- Simple scripts or utilities with no domain model
- Read-only reporting or analytics where a query builder or ORM is more appropriate
- When the overhead of abstraction exceeds the benefit (very simple single-entity apps)

## Key Concepts
- **Interface**: Define the Repository as an interface first — `UserRepository`, not `PostgresUserRepository`. Business logic depends on the interface, not the implementation.
- **Aggregate Root**: In DDD, Repositories exist per Aggregate Root — not per table. One Repository per Aggregate.
- **Collection semantics**: Repositories expose `find`, `save`, `delete` — not SQL queries. The query language stays inside the implementation.
- **Unit of Work**: Often paired with Repository to coordinate changes across multiple Repositories in a single transaction.

## In Practice
Repository is one of the most commonly applied patterns in Method engagements. It shows up in Functional Design when defining data access for domain entities, and in Code Generation as the first layer generated after the domain model. A well-defined Repository interface makes unit testing business logic trivial — mock the Repository, test the logic.

## Engineering Knowledge
💡 **Engineering Knowledge — Repository Pattern**: Abstract your data access behind a Repository interface. Business logic should never know whether it's talking to Postgres, DynamoDB, or a mock. This makes testing easier and keeps your domain model clean. Define the interface first, implement second. → `engineering-knowledge-repository/design-patterns/repository-pattern.md`

## Related Entries
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Repository is the standard DDD data access pattern
- [CQRS](../architectural-styles/cqrs.md) — typically uses Repository for the write model
- [Factory Pattern](factory-pattern.md) — often paired with Repository to construct domain objects

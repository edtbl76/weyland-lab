---
id: dependency-injection
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [solid-principles, decorator-pattern, adapter-pattern, repository-pattern]
complexity: foundational
---

# Dependency Injection (DI)

## What It Is
A technique where an object receives its dependencies from the outside rather than creating them itself. Instead of `new DatabaseRepository()` inside a service class, the repository is passed in (injected) — via constructor, method, or property. The object declares what it needs; something else (a DI container or the caller) provides it. A specific form of the broader Inversion of Control (IoC) principle.

## When to Apply
- Virtually always in object-oriented application code — DI is a baseline practice, not an advanced technique
- Whenever you want to unit test a class without its real dependencies (inject mocks)
- When the implementation of a dependency might change (inject the interface, swap implementations)
- When cross-cutting concerns are applied via decorated dependencies (logging, caching)

## When Not to Apply
- Simple scripts or utilities with no object graph to manage
- Value objects and pure functions — these have no external dependencies to inject
- Don't use a DI container where manual wiring is clearer — containers add complexity; use them when the object graph is large

## Key Concepts
- **Constructor Injection**: Dependencies declared as constructor parameters — the most explicit and testable form
- **Interface Dependency**: Inject the interface, not the implementation — the class doesn't care which concrete type it receives
- **DI Container**: A framework that constructs the object graph automatically (Spring, .NET DI, Guice, Dagger) — maps interfaces to implementations and manages lifetimes
- **Inversion of Control**: The broader principle — control of dependency creation is inverted from the class to the caller or container
- **Lifetime Management**: Singleton (one instance), Scoped (one per request), Transient (new every time)

## In Practice
DI is table stakes in modern application development. Constructor injection is the preferred form — it makes dependencies explicit and testable without a container. In Code Generation, all service classes use constructor injection. DI containers wire the application together at startup. A class that creates its own dependencies is hard to test and tightly coupled — always inject.

## Engineering Knowledge
💡 **Engineering Knowledge — Dependency Injection**: Never `new` up a dependency inside a class that has business logic. Declare what you need in the constructor, let the caller provide it. This makes the class testable (inject a mock), the dependency swappable (inject a different implementation), and the design explicit about what the class relies on. → `engineering-knowledge-repository/design-patterns/dependency-injection.md`

## Related Entries
- [SOLID Principles](../architectural-philosophy/solid-principles.md) — DI is the practical application of Dependency Inversion (the D in SOLID)
- [Decorator Pattern](decorator-pattern.md) — DI containers make decorator wiring clean
- [Adapter Pattern](adapter-pattern.md) — inject the Adapter, not the third-party library directly
- [Repository Pattern](../design-patterns/repository-pattern.md) — repositories are injected into services

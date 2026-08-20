---
id: builder-pattern
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [factory-pattern, repository-pattern]
complexity: foundational
---

# Builder Pattern

## What It Is
A creational design pattern that separates the construction of a complex object from its representation. A Builder assembles an object step-by-step, with each step returning the builder itself (fluent interface). The final `build()` call produces the completed object. Part of the Gang of Four creational patterns.

## When to Apply
- Objects with many optional parameters — avoids telescoping constructors
- Objects that require multiple assembly steps in a specific order
- When you want to enforce that an object is fully configured before it can be used
- Test data setup — builders make test fixtures readable and maintainable
- Request/response objects with conditional fields

## When Not to Apply
- Simple objects with few parameters — a constructor or factory method is cleaner
- Objects that don't benefit from step-by-step construction
- When immutability isn't a concern and direct field assignment is sufficient

## Key Concepts
- **Fluent Interface**: Each setter returns `this` (the builder), enabling method chaining: `new OrderBuilder().customer(c).items(i).discount(0.1).build()`
- **Immutable Product**: The object produced by `build()` is typically immutable — all construction happens in the builder, not after
- **Validation at build time**: The `build()` method is the right place to enforce invariants — throw if required fields are missing
- **Test Builder pattern**: A specialized application where builders are used exclusively for constructing test fixtures, keeping tests readable

## In Practice
Builder shows up most in domain model construction (complex Aggregates), request/response DTOs, and test data setup. In Code Generation, test builders are generated alongside domain models — they dramatically reduce test verbosity. A `CustomerBuilder` with sensible defaults allows tests to express only what's relevant to each scenario.

## Engineering Knowledge
💡 **Engineering Knowledge — Builder Pattern**: Objects with many optional parameters get unwieldy fast. A Builder assembles the object step-by-step with a fluent interface, validates at `build()` time, and produces an immutable result. In tests especially, Builders make fixtures readable — a test describes only what it cares about. → `engineering-knowledge-repository/design-patterns/builder-pattern.md`

## Related Entries
- [Factory Pattern](factory-pattern.md) — factory decides *what* to build; builder decides *how* to build it
- [Repository Pattern](repository-pattern.md) — builders often construct domain objects that repositories persist

---
id: factory-pattern
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [repository-pattern, strategy-pattern, domain-driven-design]
complexity: foundational
---

# Factory Pattern

## What It Is
A creational design pattern that provides an interface for creating objects without specifying the exact class to instantiate. Factories centralize and encapsulate object construction logic — callers request an object, the factory decides how to build it. Part of the Gang of Four creational patterns.

**Variants:**
- **Factory Method**: A method (often on a base class or interface) that subclasses override to create objects
- **Abstract Factory**: An interface for creating families of related objects
- **Static Factory Method**: A static method on the class itself that constructs instances (simpler, widely used)

## When to Apply
- Object construction is complex, conditional, or involves multiple steps
- You want to centralize creation logic rather than scatter `new` calls throughout the codebase
- The type of object to create varies based on configuration, context, or input
- You want to hide implementation details from callers
- Domain objects in DDD that have invariants to enforce at construction time

## When Not to Apply
- Simple objects with no construction logic — `new MyObject()` is fine
- When the pattern adds abstraction with no actual variability to manage
- Premature abstraction for objects that only ever have one implementation

## Key Concepts
- **Encapsulation of creation**: The caller doesn't know or care how the object is built
- **Invariant enforcement**: Factories are a good place to enforce that domain objects are always created in a valid state
- **Named constructors**: Static factory methods with descriptive names (`User.fromEmail()`, `Order.draft()`) are more readable than overloaded constructors

## In Practice
Factory methods appear frequently in domain model code — especially for Aggregates and Value Objects in DDD where invariants must be enforced at creation. In Code Generation, factories are generated alongside domain models and are tested first (TDD: a factory test confirms that invalid construction is rejected).

## Engineering Knowledge
💡 **Engineering Knowledge — Factory Pattern**: If constructing an object requires conditional logic, multiple steps, or invariant validation, move that logic into a factory. Named factory methods (`Order.draft()`, `Payment.fromCard()`) are more readable than constructors and make invalid states impossible to construct. → `engineering-knowledge-repository/design-patterns/factory-pattern.md`

## Related Entries
- [Repository Pattern](repository-pattern.md) — factories create domain objects; repositories persist them
- [Strategy Pattern](strategy-pattern.md) — factories often choose which strategy to instantiate
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — factories enforce Aggregate invariants at construction

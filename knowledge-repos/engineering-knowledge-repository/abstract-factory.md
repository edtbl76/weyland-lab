---
id: abstract-factory
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [factory-pattern, builder-pattern, dependency-injection, strategy-pattern]
complexity: intermediate
---

# Abstract Factory Pattern

## What It Is
A creational pattern that provides an interface for creating families of related or dependent objects without specifying their concrete classes. Where Factory Method creates one product, Abstract Factory creates a suite of related products. The client works entirely through abstract interfaces — it never references concrete classes.

## When to Apply
- Systems that must be independent of how their products are created, composed, and represented
- Systems configured with one of multiple families of products (e.g., UI toolkit themes, database adapters per vendor, cloud provider clients)
- When a family of related product objects is designed to be used together and you must enforce this constraint
- When you want to provide a class library of products and only reveal their interfaces, not their implementations

## When Not to Apply
- When only one type of object is being created — Factory Method is simpler
- When product families are unlikely to change or expand — the abstraction adds overhead
- Small codebases where the indirection of abstract factories creates unnecessary complexity

## Key Concepts
- **Abstract Factory Interface**: Declares creation methods for each distinct product type in the family
- **Concrete Factory**: Implements creation methods for a specific product family (e.g., `WindowsUIFactory`, `MacUIFactory`)
- **Abstract Product**: Interface for a type of product object (e.g., `Button`, `Checkbox`)
- **Concrete Product**: A specific implementation of a product, created by the corresponding concrete factory
- **Client**: Uses only the abstract factory and abstract product interfaces — never instantiates products directly
- **Product Family Consistency**: The abstract factory guarantees that products from one family are used together — you can't accidentally mix Windows buttons with Mac checkboxes

## In Practice
Abstract Factory appears in framework and library code more than application code. Common examples: JDBC (database driver factories), UI toolkit families, cloud provider SDK abstractions. In Method engagements, it's most useful when supporting multiple environments (cloud providers, database vendors) through a single interface. Often implemented using Dependency Injection — the concrete factory is injected rather than selected at construction time.

## Engineering Knowledge
💡 **Engineering Knowledge — Abstract Factory**: When your system needs to work with multiple families of related objects (UI themes, cloud providers, database vendors), Abstract Factory provides a single interface for creating the whole family. The client never touches concrete classes — swap the factory, swap the whole family. More complex than Factory Method; reach for it when product families are a first-class concern. → `engineering-knowledge-repository/design-patterns/abstract-factory.md`

## Related Entries
- [Factory Pattern](factory-pattern.md) — Factory Method creates one product; Abstract Factory creates a family
- [Builder Pattern](builder-pattern.md) — Builder constructs complex objects step by step; Abstract Factory creates families of objects in one step
- [Dependency Injection](dependency-injection.md) — DI containers act as configurable abstract factories

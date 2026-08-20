---
id: strategy-pattern
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [factory-pattern, observer-pattern, domain-driven-design]
complexity: foundational
---

# Strategy Pattern

## What It Is
A behavioral design pattern that defines a family of algorithms, encapsulates each one, and makes them interchangeable. The pattern lets the algorithm vary independently from the clients that use it. Instead of conditionals deciding which behavior to execute, each behavior is a class — and you swap in the right one. Part of the Gang of Four behavioral patterns.

## When to Apply
- Multiple variants of an algorithm or business rule that need to be selectable at runtime
- Complex conditionals (`if/switch`) based on type, status, or configuration that are growing
- When new behaviors need to be added without modifying existing code (Open/Closed Principle)
- Replacing type-based dispatch: `if (type == "credit") { ... } else if (type == "debit") { ... }`

## When Not to Apply
- When there is only one algorithm and no variation is expected
- When the "strategies" are simple enough that a function or lambda achieves the same result without a class hierarchy
- Premature abstraction — only introduce when variation is real, not hypothetical

## Key Concepts
- **Strategy Interface**: The contract that all strategies implement — defines the method signature
- **Concrete Strategies**: Individual implementations of the interface — each is one behavior variant
- **Context**: The class that holds a reference to a Strategy and delegates to it
- **Open/Closed Principle**: Strategy is the canonical example — open for extension (add a new strategy), closed for modification (don't change the context)

## In Practice
Strategy appears naturally when business rules vary by product type, customer segment, payment method, or any other discriminator. During Functional Design, if you find yourself writing complex conditionals to handle rule variations, that's the signal to introduce Strategy. In DDD, policies and specifications often map to Strategy implementations.

## Engineering Knowledge
💡 **Engineering Knowledge — Strategy Pattern**: If you have conditional logic that selects different behavior based on a type or status, replace it with Strategy. Each behavior variant becomes a class. Adding a new variant means adding a new class — not modifying existing code. Conditionals stop growing. → `engineering-knowledge-repository/design-patterns/strategy-pattern.md`

## Related Entries
- [Factory Pattern](factory-pattern.md) — factories often instantiate the right Strategy
- [Observer Pattern](observer-pattern.md) — behavioral patterns frequently used together
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — domain policies and specifications map to Strategy

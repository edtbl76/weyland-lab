---
id: template-method
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [strategy-pattern, factory-pattern, hook-pattern]
complexity: foundational
---

# Template Method Pattern

## What It Is
A behavioral pattern that defines the skeleton of an algorithm in a base class, deferring some steps to subclasses. The template method calls abstract operations that subclasses must implement, and optionally "hook" operations that subclasses may override. The algorithm's structure stays fixed in the base class; specific steps vary in subclasses.

## When to Apply
- Multiple classes share the same algorithm skeleton but differ in specific steps
- Refactoring similar methods across subclasses — extract the common structure into a base class
- Frameworks where users extend behavior by overriding specific steps, not the whole algorithm
- When invariant parts of an algorithm should be controlled by the base class while variable parts are customizable

## When Not to Apply
- When the algorithm structure itself varies — use Strategy instead (prefer composition over inheritance)
- Deep inheritance hierarchies that make it hard to understand which methods are overridden where
- When the variation points are numerous and complex — each variation required a new subclass, leading to class explosion

## Key Concepts
- **Template Method**: The method in the base class that defines the algorithm skeleton — typically `final` to prevent subclasses from reordering steps
- **Abstract Operation**: A step that subclasses **must** implement — no default behavior
- **Hook Operation**: A step that subclasses **may** override — has a default (often empty) implementation
- **Hollywood Principle**: "Don't call us, we'll call you" — the base class calls the subclass methods, not the other way around
- **Template Method vs. Strategy**: Template Method uses inheritance to vary behavior; Strategy uses composition. Prefer Strategy when the variation should be injectable or the object hierarchy is already complex.

## In Practice
Template Method is common in framework and library design. JUnit's `setUp()` / `tearDown()` / test method lifecycle, Spring's `JdbcTemplate`, and build tool task hierarchies all use it. In application code, the most common use is data processing pipelines: `validateInput()` → `transformData()` → `persistResult()` where the structure is fixed but each step is implementation-specific. When class hierarchies become unwieldy, refactor Template Method to Strategy.

## Engineering Knowledge
💡 **Engineering Knowledge — Template Method**: Define the algorithm once in a base class; let subclasses fill in the steps. It's the backbone of most framework extension points — JUnit lifecycle, Spring's `JdbcTemplate`, build tool tasks. Hook methods provide optional override points; abstract methods are mandatory. Watch for class explosion when too many variations require new subclasses — that's the signal to refactor from Template Method to Strategy (composition over inheritance). → `engineering-knowledge-repository/design-patterns/template-method.md`

## Related Entries
- [Strategy Pattern](strategy-pattern.md) — Template Method uses inheritance to vary steps; Strategy uses composition. Prefer Strategy as hierarchies grow.
- [Factory Pattern](factory-pattern.md) — Factory Method is a specialization of Template Method for object creation

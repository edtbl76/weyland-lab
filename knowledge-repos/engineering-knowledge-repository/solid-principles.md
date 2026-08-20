---
id: solid-principles
tags: [principle, backend]
surfaces-at: [functional-design, application-design, code-generation]
related: [dependency-injection, decorator-pattern, strategy-pattern, adapter-pattern]
complexity: foundational
---

# SOLID Principles

## What It Is
Five foundational principles of object-oriented design, coined by Robert C. Martin. They guide how to structure classes and their relationships to produce code that is maintainable, extensible, and testable. Not rules — heuristics that reveal design problems when violated.

## When to Apply
Always — SOLID principles are baseline guidance for object-oriented code, not an advanced technique. Evaluate each principle when designing classes, reviewing code, or diagnosing why code is hard to change or test.

## When Not to Apply
- Pure functional code where objects don't apply
- Simple scripts — don't over-engineer
- Taken to extremes, SOLID can produce over-abstracted code. Apply with judgment, not dogma.

## Key Concepts

**S — Single Responsibility Principle (SRP)**
A class should have one reason to change. If a class handles business logic, persistence, and HTTP responses, changes in any of those areas require modifying the class. Split them.

**O — Open/Closed Principle (OCP)**
Open for extension, closed for modification. Add new behavior by adding new code (new classes, new implementations), not by modifying existing code. Strategy and Decorator are the canonical OCP patterns.

**L — Liskov Substitution Principle (LSP)**
Subtypes must be substitutable for their base types without breaking correctness. If you have to check `instanceof` before using a subclass, LSP is violated. Prefer composition over inheritance when LSP is difficult to maintain.

**I — Interface Segregation Principle (ISP)**
Clients should not depend on interfaces they don't use. Large, fat interfaces force implementing classes to provide methods they don't need. Split interfaces into focused, role-specific ones.

**D — Dependency Inversion Principle (DIP)**
Depend on abstractions, not concretions. High-level modules should not depend on low-level modules — both should depend on interfaces. This is the theoretical basis for Dependency Injection.

## In Practice
SOLID violations are the most common source of code that's hard to test and hard to change. SRP violations produce "god classes." OCP violations produce switch statements that grow forever. DIP violations produce untestable code. During code review and Functional Design, ask: "If this requirement changes, how many places change?" The answer reveals SRP violations.

## Engineering Knowledge
💡 **Engineering Knowledge — SOLID Principles**: The five SOLID principles are your design health check. SRP: one reason to change. OCP: extend, don't modify. LSP: subtypes are interchangeable. ISP: small focused interfaces. DIP: depend on abstractions. Violations predict where code will be painful to change or test. → `engineering-knowledge-repository/architectural-philosophy/solid-principles.md`

## Related Entries
- [Dependency Injection](../design-patterns/dependency-injection.md) — the practical application of DIP
- [Strategy Pattern](../design-patterns/strategy-pattern.md) — the canonical OCP pattern
- [Decorator Pattern](../design-patterns/decorator-pattern.md) — OCP via composition
- [Adapter Pattern](../design-patterns/adapter-pattern.md) — DIP across integration boundaries

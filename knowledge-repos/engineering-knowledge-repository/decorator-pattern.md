---
id: decorator-pattern
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [adapter-pattern, facade-pattern, dependency-injection]
complexity: foundational
---

# Decorator Pattern

## What It Is
A structural design pattern that attaches additional behavior to an object dynamically by wrapping it in a decorator object that shares the same interface. Decorators compose — you can wrap a decorator in another decorator, stacking behaviors without modifying the original object. Part of the Gang of Four structural patterns.

## When to Apply
- Adding cross-cutting concerns (logging, caching, validation, retry, auth) without modifying core logic
- When behavior needs to be added or removed at runtime
- When subclassing would produce an explosion of classes for every combination of behaviors
- Middleware pipelines — HTTP middleware, command handlers with decorators

## When Not to Apply
- When the decorated object's interface needs to change — Decorator preserves the interface
- Simple cases where direct modification is cleaner and the behavior won't vary
- When the ordering of decorator application is complex enough to cause confusion

## Key Concepts
- **Shared Interface**: The decorator implements the same interface as the object it wraps — callers can't tell the difference
- **Composition over Inheritance**: Decorator achieves behavior extension through composition, not inheritance — avoids class explosion
- **Transparent Wrapping**: The decorator delegates to the wrapped object and adds behavior before or after
- **Cross-Cutting Concerns**: Logging, caching, validation, timing, and retry are natural Decorator targets — they apply across many operations without being core business logic

## In Practice
Decorators appear naturally in middleware pipelines (ASP.NET middleware, Express middleware, Spring filters) and in clean architecture where cross-cutting concerns are separated from business logic. In CQRS systems, command handlers are often decorated with logging, validation, and retry behaviors. Dependency injection containers make wiring decorators straightforward.

## Engineering Knowledge
💡 **Engineering Knowledge — Decorator Pattern**: Need to add logging, caching, or validation to an operation without touching its core logic? Wrap it in a Decorator. The caller sees the same interface; the decorator adds behavior transparently. Stack decorators to compose behaviors — no subclass explosion. → `engineering-knowledge-repository/design-patterns/decorator-pattern.md`

## Related Entries
- [Adapter Pattern](adapter-pattern.md) — structural patterns often used together
- [Dependency Injection](dependency-injection.md) — DI containers make decorator wiring clean
- [Facade Pattern](facade-pattern.md) — Facade simplifies; Decorator adds behavior

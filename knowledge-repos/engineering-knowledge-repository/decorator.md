---
id: decorator
tags: [pattern, backend, frontend]
surfaces-at: [functional-design, code-generation]
related: [hook-pattern, observer, strategy, proxy-pattern]
complexity: intermediate
---

# Decorator Pattern

## What It Is
A structural design pattern that attaches additional behavior to an object dynamically by wrapping it in a decorator object that implements the same interface. Decorators provide a flexible alternative to subclassing for extending functionality — each decorator adds a layer of behavior without modifying the original object. Multiple decorators can be stacked, composing behavior additively.

## When to Apply
- Adding cross-cutting concerns (logging, caching, auth, metrics) to objects without modifying their implementation
- When subclassing leads to a combinatorial explosion of classes
- Adding behavior that should be optional or configurable at runtime
- Extending third-party classes you cannot modify

## Key Concepts
- **Wrapping**: The decorator holds a reference to the wrapped component and delegates core behavior to it, adding its own behavior before, after, or around the delegation
- **Same Interface**: Both the component and its decorators implement the same interface — clients interact with decorated objects without knowing decorators are present
- **Composition over Inheritance**: Multiple decorators can be stacked in any order — `LoggingDecorator(CachingDecorator(AuthDecorator(service)))`. Each adds one concern
- **Python `@decorator` Syntax**: Python's function decorator syntax implements this pattern for functions — `@lru_cache`, `@login_required`, `@retry` are all decorators
- **Java/TypeScript Annotations**: `@Transactional`, `@Cacheable`, `@PreAuthorize` in Spring and similar frameworks implement decorator-like cross-cutting behavior via AOP
- **Transparency**: Well-designed decorators are transparent to the client — they fulfill the same contract as the wrapped object
- **Order Matters**: When stacking decorators, the order affects behavior — a caching decorator outside a logging decorator logs fewer calls than vice versa

## In Practice
Method codebases use Python function decorators for cross-cutting concerns (retry logic, auth checks, metrics recording). In service layer design, decorator chains are used to apply logging and rate limiting without modifying business logic. TypeScript decorator proposals are used in NestJS for route guards and interceptors.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Decorator Pattern**: Use decorators to add cross-cutting concerns (logging, caching, retries, auth) without modifying the decorated class. Decorators compose — stack them in the right order (outermost is first to intercept incoming calls). In Python, `@functools.wraps` is required to preserve metadata when writing function decorators. Prefer decorators over subclassing when you need to add behavior orthogonal to the core responsibility of the class. → `engineering-knowledge-repository/decorator.md`

## Related Entries
- [Hook Pattern](hook-pattern.md) — hooks are a related mechanism for injecting behavior at extension points
- [Observer](observer.md) — observer pattern for event-driven behavior extension
- [Strategy](strategy.md) — strategy pattern for runtime behavior swapping
- [Proxy Pattern](proxy-pattern.md) — proxy wraps an object for access control or lazy initialization

---
id: singleton
tags: [pattern, anti-pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [dependency-injection, factory-pattern]
complexity: foundational
---

# Singleton Pattern

## What It Is
A creational pattern that ensures a class has only one instance and provides a global access point to it. The class controls its own instantiation — typically through a static `getInstance()` method that returns the same instance every time. Commonly used for shared resources: logging, configuration, connection pools, caches.

## When to Apply
- Exactly one object is needed to coordinate actions across the system (logger, configuration manager, thread pool)
- The single instance must be accessible from many places without passing it explicitly
- The instance must be lazily initialized and shared

## When Not to Apply
- **Most application logic** — Singleton is one of the most frequently misused patterns. If you're reaching for Singleton, consider Dependency Injection instead.
- When it makes unit testing harder — Singletons carry global state across tests, causing test interdependence
- When the "single instance" requirement might relax (e.g., per-tenant instances in multi-tenant systems)
- In multi-threaded environments without careful double-checked locking or initialization-on-demand holder idiom

## Key Concepts
- **Single Instance**: The class stores a static reference to the sole instance and exposes it via a static method
- **Lazy Initialization**: The instance is created the first time it's requested, not at class load time
- **Thread Safety**: In multi-threaded environments, the instance must be created safely — double-checked locking or initialization-on-demand holder pattern (Java), `std::call_once` (C++), module-level initialization (Python)
- **Global State Problem**: The Singleton is effectively global state — it creates hidden dependencies and makes testing difficult
- **DI as Alternative**: An object registered as a singleton in a DI container achieves the same "one instance" goal without the global access anti-pattern — the dependency is explicit and can be mocked in tests

## In Practice
The Gang of Four Singleton pattern is useful for infrastructure concerns (logger, config, connection pool) but is frequently misapplied to domain objects, causing tight coupling and untestable code. In Method engagements, prefer DI container singletons over class-level Singletons for anything application logic touches. Reserve the classic Singleton for truly shared infrastructure where DI is not available or appropriate.

## Engineering Knowledge
💡 **Engineering Knowledge — Singleton**: Singleton ensures one instance and global access — useful for infrastructure like loggers and connection pools. But it's also one of the most misused patterns: global state makes testing hard and creates hidden coupling. Prefer registering a single instance in your DI container — you get one instance without the global access problem, and it's mockable. Reach for classic Singleton only when DI isn't available. → `engineering-knowledge-repository/design-patterns/singleton.md`

## Related Entries
- [Dependency Injection](dependency-injection.md) — preferred alternative to class-level Singleton for application objects
- [Factory Pattern](factory-pattern.md) — factory methods often create or return a singleton instance

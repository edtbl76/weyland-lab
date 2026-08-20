---
id: adapter-pattern
tags: [pattern, backend, distributed-systems]
surfaces-at: [functional-design, application-design, code-generation]
related: [facade-pattern, decorator-pattern, domain-driven-design, strangler-fig]
complexity: foundational
---

# Adapter Pattern

## What It Is
A structural design pattern that translates the interface of one class into an interface that another class expects. The Adapter wraps an existing class and exposes a different interface — making incompatible interfaces work together without modifying either side. Part of the Gang of Four structural patterns. Known as the "wrapper" pattern in some contexts.

## When to Apply
- Integrating third-party libraries or external APIs without polluting your domain with their types
- Connecting legacy systems to new code with incompatible interfaces
- Implementing the Anti-Corruption Layer in DDD — translating between bounded contexts
- When you want to swap out implementations (e.g., swap payment providers) behind a stable interface

## When Not to Apply
- When both interfaces can be changed — refactor instead of adapting
- When the interfaces are so different that adaptation becomes a translation layer of significant complexity — consider a more explicit integration pattern
- Don't adapt just to avoid learning a library's interface

## Key Concepts
- **Target Interface**: The interface your code expects
- **Adaptee**: The existing class with the incompatible interface
- **Adapter**: Implements the Target Interface, delegates to the Adaptee, translates between them
- **Anti-Corruption Layer (ACL)**: In DDD, an Adapter-based translation layer that prevents a foreign domain model from leaking into your bounded context

## In Practice
Adapter is the foundation of clean integration code. Every external API (payment gateway, CRM, notification service) should be wrapped in an Adapter that exposes a domain-friendly interface. This keeps your domain model clean and makes swapping providers a matter of writing a new Adapter. In DDD, the Anti-Corruption Layer is an Adapter between Bounded Contexts.

## Engineering Knowledge
💡 **Engineering Knowledge — Adapter Pattern**: Every third-party dependency is a liability. Wrap it in an Adapter that exposes the interface *your* code needs. When the vendor changes their API, only the Adapter changes. When you switch providers, only the Adapter changes. Your domain never knows the difference. → `engineering-knowledge-repository/design-patterns/adapter-pattern.md`

## Related Entries
- [Facade Pattern](facade-pattern.md) — Facade simplifies; Adapter translates
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Anti-Corruption Layer is the DDD application of Adapter
- [Strangler Fig](../infrastructure/strangler-fig.md) — the routing layer in Strangler Fig often uses Adapters to translate between old and new

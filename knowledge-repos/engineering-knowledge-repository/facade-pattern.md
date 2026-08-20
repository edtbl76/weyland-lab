---
id: facade-pattern
tags: [pattern, backend]
surfaces-at: [application-design, functional-design, code-generation]
related: [adapter-pattern, decorator-pattern, api-gateway-pattern]
complexity: foundational
---

# Facade Pattern

## What It Is
A structural design pattern that provides a simplified interface to a complex subsystem. The Facade doesn't add functionality — it reduces complexity by hiding the internals behind a single, coherent entry point. Clients interact with the Facade; the subsystem's complexity is invisible to them. Part of the Gang of Four structural patterns.

## When to Apply
- Complex subsystems with many classes and interactions that clients don't need to understand
- Providing a simple API over a legacy system or third-party library
- Layered architectures where each layer exposes a Facade to the layer above
- Reducing coupling between clients and subsystem internals

## When Not to Apply
- Simple subsystems where a Facade adds abstraction with no benefit
- When clients genuinely need access to subsystem internals — the Facade would become too leaky
- Don't use Facade to hide bad design — fix the underlying complexity instead

## Key Concepts
- **Simplified Interface**: The Facade exposes only what clients need — not everything the subsystem can do
- **Decoupling**: Clients depend on the Facade, not on subsystem internals — the subsystem can change without affecting clients
- **No New Behavior**: Facade delegates to the subsystem; it doesn't add logic
- **Layer Facade**: In layered architectures, service layers act as Facades over domain logic and repositories

## In Practice
Facade is one of the most natural patterns in layered architecture — a service class that orchestrates domain objects and repositories is a Facade. In Application Design, service layer definitions are Facades. In infrastructure modernization, the Strangler Fig routing layer is a Facade over the old and new systems. The API Gateway pattern is Facade at the infrastructure level.

## Engineering Knowledge
💡 **Engineering Knowledge — Facade Pattern**: If clients are navigating a complex subsystem directly, introduce a Facade. It provides one simple entry point, decouples clients from internals, and makes the subsystem replaceable behind a stable interface. Your service layer *is* a Facade — design it as one intentionally. → `engineering-knowledge-repository/design-patterns/facade-pattern.md`

## Related Entries
- [Adapter Pattern](adapter-pattern.md) — Adapter translates interfaces; Facade simplifies them
- [API Gateway Pattern](../architectural-styles/api-gateway-pattern.md) — Facade at the infrastructure level
- [Strangler Fig](../infrastructure/strangler-fig.md) — the routing proxy in Strangler Fig is a Facade

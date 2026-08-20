---
id: bridge
tags: [pattern, backend]
surfaces-at: [functional-design, application-design, code-generation]
related: [adapter-pattern, strategy-pattern, abstract-factory, dependency-injection]
complexity: intermediate
---

# Bridge Pattern

## What It Is
A structural pattern that decouples an abstraction from its implementation so that both can vary independently. Instead of using inheritance to bind an abstraction to a specific implementation, the abstraction holds a reference to an implementation object and delegates to it. This "bridge" between abstraction and implementation allows each hierarchy to grow without affecting the other.

## When to Apply
- Avoiding a permanent binding between abstraction and implementation — the implementation should be selectable at runtime
- Both the abstraction and implementation should be extensible via subclassing independently
- Changes in the implementation should not break the abstraction or its clients
- You have a proliferating class hierarchy caused by a Cartesian product of abstractions and implementations (e.g., `CircleRedShape`, `CircleBlueShape`, `SquareRedShape`…)

## When Not to Apply
- When the abstraction and implementation are already cleanly separated and there's no combinatorial explosion
- Simple systems where the added indirection of a bridge increases complexity without benefit
- When only one implementation exists and none are anticipated

## Key Concepts
- **Abstraction**: Defines the higher-level control interface and holds a reference to the Implementor
- **Refined Abstraction**: Extends the Abstraction with more specific behavior
- **Implementor**: Interface defining the primitive operations that Concrete Implementors provide
- **Concrete Implementor**: Platform-specific implementations of the Implementor interface
- **Composition over Inheritance**: Bridge is the classic example of preferring composition — the implementation is composed in, not inherited

## In Practice
Bridge prevents the "class explosion" problem. The canonical example: shapes (Circle, Square) x renderers (OpenGL, DirectX, SVG) — without Bridge, you get 6 subclasses; with Bridge, you get 2 shape classes + 3 renderer classes. In enterprise software, Bridge appears in logging frameworks (Logger abstraction + LogAppender implementations), database access layers, and notification systems (Notification abstraction + Email/SMS/Push implementors). Bridge is structurally similar to Strategy — the difference is intent: Bridge is about abstraction/implementation separation; Strategy is about interchangeable algorithms.

## Engineering Knowledge
💡 **Engineering Knowledge — Bridge Pattern**: When your class hierarchy is exploding because you're combining two orthogonal dimensions (shape × renderer, notification × channel), Bridge decouples them. The abstraction references the implementor via composition — both can be extended independently. Structurally similar to Strategy, but Bridge is about separating abstraction layers; Strategy is about interchangeable algorithms. → `engineering-knowledge-repository/design-patterns/bridge.md`

## Related Entries
- [Adapter Pattern](adapter-pattern.md) — Adapter makes incompatible interfaces work together; Bridge separates abstraction from implementation by design
- [Strategy Pattern](strategy-pattern.md) — Bridge and Strategy are structurally similar; Bridge focuses on abstraction/implementation separation, Strategy on algorithm interchangeability
- [Dependency Injection](dependency-injection.md) — DI injects the implementor into the abstraction, realizing the Bridge at runtime

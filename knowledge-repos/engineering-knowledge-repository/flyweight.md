---
id: flyweight
tags: [pattern, performance, backend]
surfaces-at: [functional-design, code-generation]
related: [prototype, composite, factory-pattern]
complexity: advanced
---

# Flyweight Pattern

## What It Is
A structural pattern that reduces memory consumption by sharing common state among many fine-grained objects. When a large number of similar objects would consume too much memory, Flyweight extracts the shared (intrinsic) state into a single shared object, while each instance holds only its unique (extrinsic) state. The client supplies the extrinsic state at runtime.

## When to Apply
- An application uses a large number of similar objects that consume significant memory
- Most object state can be made extrinsic (passed in by the context, not stored)
- Many groups of objects can be replaced by a small number of shared objects once extrinsic state is removed
- Game development (thousands of particles, bullets, trees), text rendering (character glyphs), geographic data (map tiles)

## When Not to Apply
- Small numbers of objects where memory overhead is not a concern
- When intrinsic and extrinsic state cannot be cleanly separated
- When the complexity of separating intrinsic/extrinsic state outweighs the memory savings

## Key Concepts
- **Intrinsic State**: State that is shared and immutable — stored in the Flyweight object (e.g., a character glyph's shape)
- **Extrinsic State**: State that varies per context — passed in by the client at call time, not stored in the Flyweight (e.g., a character's position on screen)
- **Flyweight Factory**: Creates and manages the pool of shared Flyweight objects — returns an existing instance if one with the same intrinsic state exists
- **Immutability**: Flyweight objects must be immutable — since they're shared, modification would affect all users
- **String Interning**: Java's `String.intern()` and Python's string interning are runtime-level Flyweight implementations

## In Practice
Flyweight is a niche optimization pattern — reach for it when profiling reveals excessive memory from large numbers of similar objects, not speculatively. The canonical examples are text editors (one glyph object per character type, shared across all occurrences) and game engines (one mesh object per tree model, rendered at thousands of positions). In modern JVM and CLR applications, the garbage collector and object pooling often address the same problem; Flyweight is more commonly seen in C++ game engines and graphics programming.

## Engineering Knowledge
💡 **Engineering Knowledge — Flyweight Pattern**: When you have thousands of similar objects eating memory, share their common state. Extract what's shared (intrinsic — the glyph shape) from what varies per instance (extrinsic — the position on screen). The Flyweight factory hands out shared instances; clients supply the extrinsic state at call time. Flyweights must be immutable. Reach for this after profiling, not speculatively. → `engineering-knowledge-repository/design-patterns/flyweight.md`

## Related Entries
- [Prototype Pattern](prototype.md) — Prototype clones objects; Flyweight shares them
- [Factory Pattern](factory-pattern.md) — Flyweight Factory manages the shared object pool
- [Composite Pattern](composite.md) — Flyweight is often used to optimize leaf nodes in a Composite tree

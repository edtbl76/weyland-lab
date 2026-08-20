---
id: prototype
tags: [design-pattern, creational, gang-of-four, cloning, object-creation, copying]
surfaces-at: [functional-design, code-generation]
related: [factory-pattern, abstract-factory, builder-pattern]
complexity: foundational
---

# Prototype Pattern

## What It Is
A creational pattern that creates new objects by copying (cloning) an existing object — the prototype. Instead of calling `new` and configuring from scratch, you copy an existing instance and modify only what differs. Useful when object construction is expensive, complex, or when the class to instantiate is specified at runtime.

## When to Apply
- Object creation is expensive (database lookup, complex computation, deep initialization) and cloning is cheaper than constructing from scratch
- The class to instantiate is determined at runtime and you want to avoid a proliferation of factory subclasses
- Objects differ only slightly from each other — start from a configured prototype and tweak
- Game development, configuration templates, document cloning, test fixture setup

## When Not to Apply
- When objects are cheap to construct — cloning adds complexity without benefit
- When objects contain references to uncloneable resources (file handles, network connections) — deep vs. shallow copy semantics must be carefully managed
- When a simple constructor call adequately expresses the construction intent

## Key Concepts
- **Clone Method**: The core operation — each prototype class implements a `clone()` or `copy()` method
- **Shallow Copy**: Copies the object's fields by reference — nested objects are shared with the original
- **Deep Copy**: Recursively copies all nested objects — the clone is fully independent of the original
- **Prototype Registry**: A store of named prototype instances that can be cloned on demand — acts as a catalog of template objects
- **Copy Constructor**: An alternative to `clone()` in languages without native prototype support

## In Practice
Prototype is common in test setup (creating pre-configured test fixtures by cloning a base object), configuration management (environment-specific config derived from a base template), and game development (spawning enemies with slight variations). In most modern languages, copy constructors or explicit clone methods are preferred over `Object.clone()` due to its well-known pitfalls in Java. The key discipline is deciding shallow vs. deep copy for each object — document the intent explicitly.

## Engineering Knowledge
💡 **Engineering Knowledge — Prototype Pattern**: When creating an object from scratch is expensive or complex, clone an existing one. Start with a configured prototype, copy it, and adjust only what differs. Be deliberate about shallow vs. deep copy — shared references in a shallow clone can cause unexpected mutations. Common in test fixture setup and game object spawning. → `engineering-knowledge-repository/design-patterns/prototype.md`

## Related Entries
- [Factory Pattern](factory-pattern.md) — Factory Method and Prototype both solve object creation; Prototype clones, Factory constructs
- [Abstract Factory](abstract-factory.md) — Abstract Factory creates families; Prototype registry can serve a similar role with clone-based instantiation
- [Builder Pattern](builder-pattern.md) — Builder constructs step by step; Prototype copies a complete existing configuration

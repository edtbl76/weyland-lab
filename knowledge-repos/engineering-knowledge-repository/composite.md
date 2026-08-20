---
id: composite
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [iterator, visitor, decorator-pattern, strategy-pattern]
complexity: intermediate
---

# Composite Pattern

## What It Is
A structural pattern that composes objects into tree structures to represent part-whole hierarchies. Clients treat individual objects (leaves) and compositions of objects (nodes) uniformly through the same interface. The key insight: a node and a leaf respond to the same operations — the node delegates to its children; the leaf executes directly.

## When to Apply
- Representing hierarchies: file systems (files and directories), UI component trees, organizational charts, expression trees, menus
- When clients should be able to ignore the difference between compositions of objects and individual objects
- When the hierarchy can be arbitrarily deep and the same operations apply at every level

## When Not to Apply
- Flat structures with no nesting — the pattern adds unnecessary abstraction
- When leaf and composite behaviors are so different that a common interface is forced and awkward
- When type safety requires distinguishing leaves from composites — the uniform interface can obscure type information

## Key Concepts
- **Component**: The common interface for both leaves and composites — defines operations like `render()`, `calculate()`, `execute()`
- **Leaf**: A basic element with no children — implements the Component interface directly
- **Composite**: A container that holds children (both Leaf and Composite) — delegates operations to each child
- **Uniform Treatment**: The client calls the same method regardless of whether it's dealing with a single leaf or a subtree
- **Recursive Composition**: The Composite delegates to children, which may themselves be Composites — operations naturally recurse through the tree

## In Practice
Composite is the structural backbone of most UI frameworks (React's component tree, HTML DOM), build systems (tasks with subtasks), and document object models. In domain modeling, Composite appears in product catalogs (products vs. bundles), organizational structures, and workflow definitions. The pattern pairs naturally with Visitor (to perform operations on the tree) and Iterator (to traverse it).

## Engineering Knowledge
💡 **Engineering Knowledge — Composite Pattern**: File systems, UI trees, and org charts all share the same structure: nodes that contain other nodes or leaves. Composite lets you treat them uniformly — call `render()` on a single button or an entire panel; the panel delegates to its children. The power is recursive composition: you can nest arbitrarily deep without the client caring. Pairs naturally with Visitor for tree traversal operations. → `engineering-knowledge-repository/design-patterns/composite.md`

## Related Entries
- [Visitor Pattern](visitor.md) — Visitor applies operations to every node in a Composite tree
- [Iterator Pattern](iterator.md) — Iterator traverses Composite structures uniformly
- [Decorator Pattern](decorator-pattern.md) — Decorator wraps a single Component; Composite aggregates many Components

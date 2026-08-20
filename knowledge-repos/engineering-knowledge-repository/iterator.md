---
id: iterator
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [composite, visitor]
complexity: foundational
---

# Iterator Pattern

## What It Is
A behavioral pattern that provides a way to sequentially access elements of a collection without exposing its underlying representation. The iterator encapsulates the traversal logic — the client calls `hasNext()` / `next()` (or the language equivalent) without knowing whether it's walking an array, a linked list, a tree, or a database cursor.

## When to Apply
- Providing a standard way to traverse different types of collections
- Hiding the internal structure of a collection from its consumers
- Supporting multiple simultaneous traversals of the same collection (multiple iterator instances)
- When you want to provide a uniform traversal interface across heterogeneous data sources (collections, streams, database results)

## When Not to Apply
- Language-native iteration constructs (for-each, streams, generators) already handle the use case — don't implement a custom iterator when the language provides one
- Simple single-loop array traversal — native indexing is clearer

## Key Concepts
- **Iterator Interface**: Declares `hasNext()`, `next()`, and optionally `remove()` — the minimal traversal protocol
- **Concrete Iterator**: Implements traversal for a specific collection type — tracks current position
- **Aggregate (Collection) Interface**: Declares a method to create an Iterator
- **External Iterator**: The client controls the iteration — calls `next()` explicitly (Java `Iterator`, C++ range iterator)
- **Internal Iterator**: The collection controls iteration — the client provides a callback (JavaScript `Array.forEach`, Ruby `each`, Python `map`)
- **Language Integration**: Every modern language bakes Iterator into the runtime. Java `Iterable`, Python `__iter__`/`__next__`, C# `IEnumerable`, JavaScript `Symbol.iterator` are all formalizations of this pattern.

## In Practice
Iterator is the most language-integrated of the GoF patterns — you use it constantly without thinking about it. The explicit design value shows when implementing custom data structures (trees, graphs, lazy sequences) that need to integrate with `for-each` loops. In Method engagements, it's most visible when building domain-specific collections or streaming database result sets as an iterator rather than materializing the full result set in memory.

## Engineering Knowledge
💡 **Engineering Knowledge — Iterator Pattern**: Every `for-each` loop uses this pattern — it's baked into every language runtime. The value is when you build custom data structures: implement the language's iterator protocol (`Iterable` in Java, `__iter__` in Python) and your collection works seamlessly with all standard library traversal. For large datasets, iterator-based traversal streams data without materializing everything in memory. → `engineering-knowledge-repository/design-patterns/iterator.md`

## Related Entries
- [Composite Pattern](composite.md) — Iterator traverses Composite tree structures
- [Visitor Pattern](visitor.md) — Visitor applies operations while Iterator traverses; often used together

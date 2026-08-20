---
id: visitor
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [composite, iterator, strategy-pattern]
complexity: advanced
---

# Visitor Pattern

## What It Is
A behavioral pattern that lets you add new operations to an object structure without modifying the classes of the elements it operates on. You define a Visitor class with a `visit` method for each element type; each element accepts the visitor and dispatches to the appropriate `visit` method. This is double-dispatch: the operation to execute depends on both the visitor type and the element type.

## When to Apply
- An object structure contains many classes of objects with differing interfaces, and you need to perform operations on these objects that depend on their concrete classes
- Many distinct and unrelated operations need to be performed on an object structure, and you don't want to pollute the classes with these operations
- The classes in the object structure rarely change, but you often define new operations on the structure
- AST traversal (compilers, query parsers), document export (HTML, PDF, Markdown), code analysis tools, report generation

## When Not to Apply
- When new element types are added frequently — every new element requires updating every Visitor (breaks the Open/Closed Principle for element additions)
- When the element hierarchy is shallow or there are few element types — simpler alternatives exist
- When encapsulation of element internals is critical — Visitors often need access to element internal state

## Key Concepts
- **Visitor Interface**: Declares a `visit` method for each Concrete Element type — `visitCircle(Circle c)`, `visitSquare(Square s)`
- **Concrete Visitor**: Implements operations for each element type — one Visitor per operation (AreaCalculator, Renderer, Serializer)
- **Element Interface**: Declares an `accept(Visitor v)` method
- **Concrete Element**: Implements `accept` by calling `visitor.visitConcreteElement(this)` — this is the double-dispatch
- **Double Dispatch**: The operation is dispatched first on the element's runtime type (to call the right `accept`), then on the visitor's type (to call the right `visit` method)
- **Open/Closed Tradeoff**: Adding new operations is easy (new Visitor class); adding new element types is hard (all Visitors must be updated)

## In Practice
Visitor is most naturally used in compiler and interpreter design (AST node visitors for type-checking, code generation, optimization passes) and document processing (export to multiple formats). In Method engagements, Visitor appears in reporting systems (generating different output formats from a common domain model) and workflow processing (applying different validations or transformations to different step types). Modern languages with pattern matching (Rust `match`, Kotlin `when`, Haskell) achieve the same effect more elegantly than classical Visitor.

## Engineering Knowledge
💡 **Engineering Knowledge — Visitor Pattern**: Add new operations to a stable object hierarchy without touching the element classes. Each Visitor encapsulates one operation across all element types — add a new Visitor, not new methods to every element class. The tradeoff: adding new element types is painful (every Visitor must be updated). Use when the element structure is stable and new operations are frequent — compilers, AST traversal, document export. Languages with pattern matching do this more cleanly. → `engineering-knowledge-repository/design-patterns/visitor.md`

## Related Entries
- [Composite Pattern](composite.md) — Visitor is often applied to traverse and operate on Composite trees
- [Iterator Pattern](iterator.md) — Iterator traverses; Visitor applies operations during traversal
- [Strategy Pattern](strategy-pattern.md) — Strategy selects one algorithm for one object; Visitor applies potentially different logic per element type in a structure

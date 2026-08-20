---
id: property-based-testing
tags: [methodology, testing]
surfaces-at: [code-generation]
related: [mutation-testing, test-doubles, shift-left-testing]
complexity: advanced
---

# Property-Based Testing

## What It Is
A testing technique where instead of writing specific input-output examples, you define *properties* — invariants that must hold true for all valid inputs — and a framework generates hundreds or thousands of random inputs to try to falsify them. When a property fails, the framework automatically shrinks the failing case to the minimal reproducing example. Originally popularized by Haskell's QuickCheck; now available in virtually all languages.

## When to Apply
- Algorithms with mathematical properties (sorting, parsing, encoding/decoding)
- Business logic with invariants that should hold across all inputs (e.g., total = sum of line items)
- Functions that should be invertible (serialize → deserialize = original)
- Code that processes user-supplied input with wide value ranges
- When edge cases are hard to enumerate manually

## When Not to Apply
- UI and integration tests — property-based testing works best for pure functions
- When properties are hard to express — if you can only express "correct output for this specific input," use example-based tests
- Code with extensive external side effects — generators need pure or mockable interfaces

## Key Concepts
- **Property**: An invariant expressed as a function that returns true/false — e.g., `sort(list).length === list.length` or `decode(encode(x)) === x`
- **Generator**: A composable description of how to randomly produce inputs of a given type — arbitrary strings, integers within range, lists of objects
- **Shrinking**: When a test fails, the framework automatically reduces the failing input to the simplest possible case that still fails — makes debugging tractable
- **QuickCheck**: The original property-based testing library (Haskell); the model for all successors
- **fast-check**: The leading JavaScript/TypeScript property-based testing library — integrates with Jest/Vitest
- **Hypothesis**: The leading Python property-based testing library — stateful testing support, example database
- **jqwik**: JVM (Java/Kotlin) property-based testing framework integrated with JUnit 5
- **Stateful Property Testing**: Testing sequences of operations rather than single function calls — verifies that invariants hold across state transitions

## In Practice
Property-based testing is most valuable for parsing, serialization, financial calculations, and data transformation pipelines. In Method engagements, property-based tests are used alongside example-based tests — not as a replacement. Define 3-5 core properties for critical business logic modules. `fast-check` for TypeScript services; `jqwik` for Java/Kotlin.

## Engineering Knowledge
💡 **Engineering Knowledge — Property-Based Testing**: Instead of writing specific examples, define invariants: "for all valid inputs, property X holds." The framework generates thousands of random inputs trying to break your property — and shrinks failures to minimal reproducers. Excellent for serialization roundtrips, sorting algorithms, financial calculations, and any logic with mathematical invariants. Use `fast-check` (TypeScript), `Hypothesis` (Python), or `jqwik` (Java). Complement example-based tests; don't replace them. → `engineering-knowledge-repository/testing/property-based-testing.md`

## Related Entries
- [Mutation Testing](mutation-testing.md) — another technique for verifying test suite quality
- [Test Doubles](test-doubles.md) — property-based tests often need clean interfaces for generators to work
- [Shift-Left Testing](shift-left-testing.md) — property-based testing finds edge cases early in development

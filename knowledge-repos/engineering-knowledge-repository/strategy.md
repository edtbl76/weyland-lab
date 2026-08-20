---
id: strategy
tags: [pattern, backend, frontend]
surfaces-at: [functional-design, code-generation]
related: [hook-pattern, decorator, observer, dependency-injection]
complexity: beginner
---

# Strategy Pattern

## What It Is
A behavioral design pattern that defines a family of algorithms, encapsulates each one, and makes them interchangeable. Strategy lets the algorithm vary independently from the clients that use it. Rather than implementing multiple behaviors with conditionals (`if algorithm == 'A': ...`), each algorithm is encapsulated in its own class/function that implements a common interface. The client holds a reference to the current strategy and delegates algorithm execution to it.

## When to Apply
- When you have multiple variants of an algorithm and want to switch between them at runtime
- Replacing large conditionals that select behavior based on type or mode
- When algorithm implementation details should be hidden from the client
- Enabling unit testing of algorithms in isolation

## Key Concepts
- **Strategy Interface**: Defines the contract all concrete strategies must implement. The client depends on this interface, not on concrete implementations
- **Concrete Strategies**: Individual implementations of the strategy interface — each encapsulates one algorithm or behavior variant
- **Context**: The object that holds a reference to the current strategy and delegates algorithm calls to it. The context can accept strategies via constructor injection or a setter
- **Runtime Swapping**: The strategy can be changed at runtime by replacing the strategy reference on the context — behavior changes without modifying the context's code
- **Eliminating Conditionals**: Replaces `if/elif/switch` chains with polymorphic dispatch. Adding a new algorithm means adding a new strategy class, not modifying existing code (Open/Closed Principle)
- **First-Class Functions**: In languages with first-class functions (Python, JavaScript), strategies can be plain functions/lambdas rather than full classes — simpler for small algorithms
- **Examples**: Sorting algorithms, payment processors (`CreditCardStrategy`, `PayPalStrategy`), compression algorithms, pricing rules, validation logic

## In Practice
Method uses the strategy pattern for pluggable ML preprocessing steps, payment provider abstraction, and notification channel selection. In Python, strategies are implemented as callables (functions or classes with `__call__`) for maximum flexibility. Dependency injection frameworks register strategies and inject the appropriate implementation based on configuration.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Strategy Pattern**: Replace algorithm-selecting conditionals with strategy objects that share a common interface. The client shouldn't know or care which algorithm it's using — it just calls the interface. In Python/JavaScript, a function reference is a valid strategy — you don't always need a full class. Combine with dependency injection to select strategies from configuration rather than code. New algorithms = new strategy implementations, no changes to existing code. → `engineering-knowledge-repository/strategy.md`

## Related Entries
- [Hook Pattern](hook-pattern.md) — hooks are extension points; strategy is algorithm selection — related but distinct purposes
- [Decorator](decorator.md) — decorator adds behavior around an object; strategy replaces algorithm behavior within
- [Observer](observer.md) — observer distributes state change events; strategy selects how to process them
- [Dependency Injection](dependency-injection.md) — DI is commonly used to inject the selected strategy into the context

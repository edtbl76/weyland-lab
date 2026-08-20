---
id: command-pattern
tags: [pattern, backend]
surfaces-at: [functional-design, code-generation]
related: [cqrs, strategy-pattern, decorator-pattern, observer-pattern]
complexity: foundational
---

# Command Pattern

## What It Is
A behavioral design pattern that encapsulates a request as an object. The Command object contains all the information needed to perform an action — the receiver, the method to call, and the parameters. The invoker triggers commands without knowing what they do. Part of the Gang of Four behavioral patterns.

## When to Apply
- Operations that need to be queued, logged, or scheduled
- Undo/redo functionality — each Command stores enough state to reverse itself
- Decoupling the object that invokes an operation from the object that performs it
- CQRS — Commands are the write side of the pattern
- Transactional operations that need rollback support
- Pipelines where commands are decorated with cross-cutting concerns

## When Not to Apply
- Simple direct method calls with no need for queuing, logging, or undo
- When the Command encapsulates so little logic that it's just indirection for its own sake

## Key Concepts
- **Command**: An object with an `execute()` method and all the data needed to perform the operation
- **Invoker**: Calls `execute()` on the Command — doesn't know or care what it does
- **Receiver**: The object that does the actual work
- **Command Handler**: In CQRS, a dedicated class that handles one specific Command type — contains the business logic
- **Command Bus**: A dispatcher that routes Commands to their handlers — enables middleware decoration

## In Practice
Command is the code-level expression of CQRS. In modern applications, a Command Bus routes Commands to Command Handlers, which are decorated with logging, validation, and authorization using the Decorator pattern. This produces clean, single-responsibility handlers that are easy to test. In Code Generation, each user action maps to a Command with a corresponding Handler.

## Engineering Knowledge
💡 **Engineering Knowledge — Command Pattern**: Encapsulate user intentions as Command objects. Each command carries its data and is handled by a dedicated Command Handler. This separates what the user wants to do from how it's done, enables logging and validation through decoration, and maps cleanly onto CQRS. → `engineering-knowledge-repository/design-patterns/command-pattern.md`

## Related Entries
- [CQRS](../architectural-styles/cqrs.md) — Commands are the write side of CQRS
- [Decorator Pattern](decorator-pattern.md) — Command Handlers are commonly decorated with cross-cutting concerns
- [Strategy Pattern](strategy-pattern.md) — behavioral patterns frequently used together

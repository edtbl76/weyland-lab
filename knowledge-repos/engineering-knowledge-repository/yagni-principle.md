---
id: yagni-principle
tags: [principle, backend]
surfaces-at: [functional-design, application-design, code-generation]
related: [dry-principle, solid-principles, evolutionary-architecture, kiss-principle]
complexity: foundational
---

# YAGNI — You Aren't Gonna Need It

## What It Is
An Extreme Programming principle stating: "Always implement things when you actually need them, never when you just foresee that you need them." Coined by Ron Jeffries. YAGNI is a direct counter to speculative generality — building abstractions, extension points, or capabilities for requirements that don't yet exist. The cost of building unused code is always real; the value of hypothetical future requirements is always speculative.

## When to Apply
- When considering adding an abstraction layer "in case we need flexibility later"
- When building configurability or plugin systems for variations that haven't been requested
- When adding parameters or options to handle scenarios that may never occur
- When designing for future scale that current data doesn't justify

## When Not to Apply
- **Known, imminent requirements**: If requirements are confirmed and arriving in the next sprint, building toward them now is planning, not speculation.
- **Security and compliance foundations**: Infrastructure for security, audit logging, and compliance is harder to retrofit — build it early even when it feels premature.
- **Architectural seams**: Creating clean module boundaries is cheap and pays structural dividends — it's not the same as speculative feature code.

## Key Concepts
- **Speculative Generality**: Building abstractions or extension points for requirements that only might arrive — the opposite of YAGNI
- **Cost of Unused Code**: Every line of speculative code has a carrying cost — it must be tested, maintained, understood by new engineers, and worked around when it doesn't quite fit the real requirement when it finally arrives
- **Simplest Thing That Could Possibly Work**: The XP companion heuristic — when implementing, choose the simplest design that satisfies current requirements
- **Refactoring Safety Net**: YAGNI works when you have tests and can refactor safely. In a codebase without tests, adding future flexibility up front may be pragmatically justified.

## In Practice
YAGNI violations are among the most common sources of unnecessary complexity in codebases Method inherits from clients. The tell: "we might need to support X later" or "what if we want to swap Y?" When auditing existing code, YAGNI violations often manifest as elaborate plugin systems with one implementation, abstract base classes with one subclass, and factory registries that create two types. Delete the unused complexity — it's not a safety net, it's ballast.

## Engineering Knowledge
💡 **Engineering Knowledge — YAGNI**: Don't build it until you need it. Every speculative abstraction, extension point, or configurability option has a real carrying cost — maintenance, cognitive load, wrong fit when the real requirement finally arrives. Implement the simplest thing that satisfies current requirements; refactor when the real need emerges. YAGNI works when you have tests. The corollary: code you deleted today is code you don't have to maintain tomorrow. → `engineering-knowledge-repository/architectural-philosophy/yagni-principle.md`

## Related Entries
- [DRY Principle](dry-principle.md) — DRY prevents duplication; YAGNI prevents speculative abstraction
- [Evolutionary Architecture](evolutionary-architecture.md) — evolutionary thinking embraces YAGNI — evolve the design as requirements clarify
- [SOLID Principles](solid-principles.md) — Open/Closed Principle creates extension points; YAGNI counsels restraint in creating them

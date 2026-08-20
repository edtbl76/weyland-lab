---
id: kiss-principle
tags: [principle, backend]
surfaces-at: [application-design, functional-design, code-generation]
related: [yagni-principle, dry-principle, separation-of-concerns, law-of-demeter]
complexity: foundational
---

# KISS Principle

## What It Is
Keep It Simple, Stupid (or: Keep It Simple and Straightforward). A design principle originating in the US Navy in the 1960s, stating that systems work best when they are kept simple rather than made complex. In software, KISS is the antidote to accidental complexity — complexity introduced not by the problem itself but by the solution. The most elegant solution to a problem is usually the simplest one that satisfies the requirements.

## When to Apply
- Always — simplicity is a default posture, not a situational choice
- When designing an architecture, data model, or API — prefer the simpler option if it meets requirements
- When reviewing code — if the logic is hard to follow, it is probably too complex
- When choosing between two solutions of equal capability

## Key Concepts
- **Essential vs. Accidental Complexity**: Essential complexity is inherent to the problem (a payroll system is inherently complex). Accidental complexity is introduced by the solution — unnecessary abstractions, premature optimization, over-engineering. KISS targets accidental complexity
- **Simple ≠ Simplistic**: Simple means easy to understand and reason about. Simplistic means naive and insufficient. KISS advocates for the former, not the latter
- **Cognitive Load**: Simpler code reduces the cognitive load required to understand, maintain, and debug it. Lower cognitive load = fewer bugs, faster onboarding, easier reviews
- **Relationship to YAGNI**: YAGNI says don't build what you don't need. KISS says build what you need as simply as possible. They are complementary — YAGNI limits scope; KISS limits complexity within scope
- **Relationship to DRY**: DRY can conflict with KISS — creating a shared abstraction to eliminate duplication sometimes adds complexity. Three clear, simple copies may be better than one complex abstraction. Apply DRY when duplication causes maintenance problems, not reflexively
- **Flat Over Nested**: Prefer flat data structures and logic over deeply nested ones. A flat conditional chain is easier to understand than nested conditionals three levels deep
- **Boring Technology**: Choosing established, well-understood technology over novel alternatives is KISS applied to architecture — the team already knows how it works, failure modes are understood

## In Practice
Method engineering reviews flag accidental complexity: unnecessary abstraction layers, over-engineered state machines for simple flows, complex inheritance hierarchies where composition would be simpler. Code review culture asks "is there a simpler way to do this?" Code that requires a long explanation to understand is a candidate for simplification.

## Engineering Knowledge
💡 **Engineering Knowledge — KISS Principle**: Complexity is the enemy. Every unnecessary abstraction, pattern, or layer of indirection makes the system harder to understand, debug, and change. Ask: is this the simplest thing that could work? Simple code is easier to review, test, and maintain. Prefer boring, well-understood technology — its failure modes are known. KISS and YAGNI are companions: YAGNI limits what you build; KISS limits how complex you build it. When in doubt, the simpler solution is usually the right one. → `engineering-knowledge-repository/architectural-philosophy/kiss-principle.md`

## Related Entries
- [YAGNI Principle](yagni-principle.md) — YAGNI limits scope; KISS limits complexity within that scope
- [DRY Principle](dry-principle.md) — DRY can conflict with KISS when eliminating duplication requires complex abstraction
- [Separation of Concerns](separation-of-concerns.md) — proper separation is a KISS enabler — each part is simpler in isolation
- [Law of Demeter](law-of-demeter.md) — Law of Demeter promotes KISS by reducing coupling and knowledge dependencies

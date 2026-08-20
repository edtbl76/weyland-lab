---
id: dry-principle
tags: [principle, backend]
surfaces-at: [functional-design, code-generation, application-design]
related: [solid-principles, yagni-principle, separation-of-concerns]
complexity: foundational
---

# DRY — Don't Repeat Yourself

## What It Is
The principle that "every piece of knowledge must have a single, unambiguous, authoritative representation within a system." Coined by Andrew Hunt and David Thomas in The Pragmatic Programmer. DRY is not just about avoiding duplicate code — it's about eliminating duplicate *knowledge*. When the same concept is represented in multiple places, changing that concept requires finding and updating every representation — a fertile source of bugs.

## When to Apply
- Business rules encoded in multiple places — centralize in one authoritative location
- Data transformations duplicated across service methods — extract to a shared transformer
- Configuration values copied across files — centralize in a single config source
- Validation logic scattered across layers — define once, call everywhere

## When Not to Apply
- **Premature abstraction is the greater risk.** Not all duplicate code represents the same *knowledge*. Two code fragments may look identical today but evolve independently — forcing a premature abstraction couples them artificially. The "Rule of Three" is a practical heuristic: refactor to eliminate duplication on the third occurrence, not the second.
- **Test code**: Tests often benefit from a degree of intentional duplication (explicit setup over shared helpers) to make each test self-explanatory. Excessive DRY in tests creates fragile, hard-to-read test suites.
- **Microservices boundaries**: DRY across service boundaries often creates coupling. Each service owning its own copy of shared types is often the correct tradeoff.

## Key Concepts
- **Knowledge Duplication vs. Code Duplication**: Two functions that accidentally look the same are not DRY violations if they represent different concepts. The test: if one changes, must the other change too? If yes — DRY violation. If no — acceptable duplication.
- **WET**: Write Everything Twice (or "We Enjoy Typing") — the ironic name for the anti-DRY pattern
- **Rule of Three**: A pragmatic heuristic — if you write something a third time, that's the signal to extract it. Once is unique, twice is coincidence, three times is a pattern.
- **DRY in Data**: A single source of truth for data — no denormalization until performance demands it; no duplicated derived state when it can be computed

## In Practice
DRY is one of the most frequently misapplied principles. The failure mode is over-abstraction: developers eliminate *apparent* duplication between code that actually represents different concepts, creating a single coupled abstraction that's harder to evolve than the original duplication. Kent Beck's "duplication is cheaper than the wrong abstraction" is the corrective. Apply DRY confidently to business rules and domain knowledge; apply it cautiously to code that happens to look the same.

## Engineering Knowledge
💡 **Engineering Knowledge — DRY Principle**: Every piece of knowledge should have one authoritative home. Duplication in business rules is dangerous — change it in one place, miss it in another, introduce a bug. But not all code duplication is a DRY violation: two similar functions that evolve independently should stay separate. Kent Beck: "duplication is cheaper than the wrong abstraction." Use the Rule of Three — refactor on the third occurrence, not the second. → `engineering-knowledge-repository/architectural-philosophy/dry-principle.md`

## Related Entries
- [SOLID Principles](solid-principles.md) — DRY and SOLID are complementary code-level principles
- [YAGNI Principle](yagni-principle.md) — YAGNI prevents premature abstraction; DRY prevents premature duplication
- [Separation of Concerns](separation-of-concerns.md) — SOC defines clear ownership boundaries that prevent knowledge duplication

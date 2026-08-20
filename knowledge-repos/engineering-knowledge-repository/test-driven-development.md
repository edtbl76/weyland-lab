---
id: test-driven-development
tags: [methodology, testing]
surfaces-at: [functional-design, code-generation]
related: [behavior-driven-development, contract-testing]
complexity: foundational
---

# Test-Driven Development (TDD)

## What It Is
A development practice where tests are written before the code that makes them pass. The cycle is: **Red** (write a failing test) → **Green** (write the minimum code to pass it) → **Refactor** (clean up without breaking the test). TDD is a design practice as much as a testing practice — it forces you to think about interfaces before implementation.

## When to Apply
- Complex business logic where correctness is critical
- Code with many edge cases or branching conditions
- When refactoring existing code — tests provide a safety net
- When the interface (how code is called) matters as much as the implementation
- New greenfield units with well-understood requirements

## When Not to Apply
- Highly exploratory work where the design is unknown — spike first, then TDD
- Simple pass-through code with no logic (getters, setters, thin controllers)
- UI code with rapidly changing layouts — integration/e2e tests are more stable there
- When the team is unfamiliar with TDD and there is no time to learn — forced TDD without understanding produces poor tests

## Key Concepts
- **Red-Green-Refactor**: The fundamental loop. Never skip the refactor step — that's where design improvement happens.
- **Test as specification**: A TDD test describes what the code *should do*, not how it does it. Tests become living documentation.
- **Small steps**: Each cycle should be tiny — minutes, not hours. If a test takes too long to make pass, break it down further.
- **Triangulation**: Write multiple tests from different angles to converge on the correct implementation.

## In Practice
TDD shapes the code generation plan — tests are written first for each component, then implementation follows. In Functional Design, TDD thinking helps surface edge cases and validation rules early, before any code is written. A team that TDDs consistently finds that their Functional Design questions are sharper because they're already thinking about failure cases.

## Engineering Knowledge
💡 **Engineering Knowledge — Test-Driven Development**: Before writing implementation code, write a failing test that describes the behavior. This forces clarity on the interface and surfaces edge cases early — often revealing missing requirements before they become bugs. → `engineering-knowledge-repository/methodologies/test-driven-development.md`

## Related Entries
- [Behavior-Driven Development](behavior-driven-development.md) — BDD extends TDD with business-readable test syntax
- [Contract Testing](../testing/contract-testing.md) — TDD at the service boundary level

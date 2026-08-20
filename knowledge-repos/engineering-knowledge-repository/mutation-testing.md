---
id: mutation-testing
tags: [methodology, testing]
surfaces-at: [code-generation]
related: [test-doubles, load-testing, chaos-engineering, shift-left-testing]
complexity: advanced
---

# Mutation Testing

## What It Is
A technique for measuring test suite quality by automatically introducing small, targeted changes (mutations) to the source code — flipping a `>` to `>=`, negating a boolean, changing an arithmetic operator — and checking whether existing tests detect the change. A mutation that isn't caught by any test (a "surviving mutant") exposes a gap in test coverage that line coverage metrics would miss. The goal: kill all mutants.

## When to Apply
- High-value business logic where test quality is critical (payment processing, authorization, calculations)
- After achieving high line/branch coverage but wanting to verify coverage is meaningful
- When teams want to identify which tests are actually contributing to defect detection
- As part of a quality gate in CI for critical modules

## When Not to Apply
- UI, integration, or infrastructure code where mutation testing tools have limited support
- When the test suite is already slow — mutation testing multiplies run time (each mutant = one test run)
- As a blanket standard across an entire large codebase — target high-value modules selectively

## Key Concepts
- **Mutant**: A modified version of the source code with a single small change — a syntax-level fault injection
- **Killed Mutant**: A mutation caught by at least one test — the test suite is effective against this fault type
- **Surviving Mutant**: A mutation not caught by any test — reveals a gap in test coverage or assertion strength
- **Mutation Score**: `(killed mutants / total mutants) × 100%`. A score of 80%+ is a common target for critical modules
- **Equivalent Mutant**: A mutation that changes syntax but not semantics — these cannot be killed by any test. Mutation tools try to filter these automatically
- **PIT (PITest)**: The dominant mutation testing tool for JVM languages (Java, Kotlin). Configurable mutators, incremental mutation to reduce run time
- **Stryker**: Mutation testing for JavaScript/TypeScript (Stryker Mutator) and .NET (Stryker.NET)
- **Test Strength vs. Coverage**: 100% line coverage with weak assertions (asserting only that no exception is thrown) can have a 20% mutation score — mutation testing exposes this

## In Practice
Method uses mutation testing selectively on high-value domain logic modules rather than the full codebase. PITest is used for Java/Kotlin services. Mutation score targets are established per module (80% for core business logic). Run mutation testing outside of the main CI loop (too slow for every commit) — schedule nightly or on PRs touching critical modules.

## Engineering Knowledge
💡 **Engineering Knowledge — Mutation Testing**: Line coverage tells you which code was executed; mutation testing tells you which code was *verified*. A test that doesn't assert anything kills no mutants. Use PITest (JVM) or Stryker (JS/.NET) on high-value business logic modules. Target 80%+ mutation score for critical code. Don't run it on the whole codebase — too slow. A surviving mutant in payment or auth logic is a real defect risk. → `engineering-knowledge-repository/testing/mutation-testing.md`

## Related Entries
- [Shift-Left Testing](shift-left-testing.md) — mutation testing identifies gaps before production
- [Test Doubles](test-doubles.md) — effective mocks and stubs are needed for mutations to be isolated
- [Load Testing](load-testing.md) — complementary test quality technique for non-functional behavior

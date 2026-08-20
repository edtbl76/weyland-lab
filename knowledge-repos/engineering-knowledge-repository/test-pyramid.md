---
id: test-pyramid
tags: [reference, testing]
surfaces-at: [nfr-requirements, functional-design, code-generation]
related: [test-driven-development, behavior-driven-development, contract-testing]
complexity: foundational
---

# Test Pyramid

## What It Is
A model for structuring a test suite that prioritizes a large base of fast, isolated unit tests, a middle layer of integration tests that verify component interactions, and a small apex of slow end-to-end tests that verify full user journeys. Originally described by Mike Cohn. The pyramid shape reflects the recommended proportion: many unit tests, fewer integration tests, very few E2E tests. An inverted pyramid (many E2E, few unit tests) is a common anti-pattern called the "ice cream cone."

## When to Apply
- Any system with an automated test suite — the pyramid is a universal test strategy model
- When defining testing strategy during NFR Requirements or Functional Design
- When a test suite is slow or fragile — diagnose against the pyramid to find the over-reliance on E2E tests
- When onboarding a team to testing discipline (unit → integration → E2E mental model)

## When Not to Apply
- Not a rigid rule — the right proportions depend on system characteristics. API-heavy systems may have more integration tests; pure algorithmic systems may have almost all unit tests.
- Don't use the pyramid to justify having zero E2E tests — some coverage of critical user journeys is essential
- Microservices with many service boundaries may favor the "testing honeycomb" model (more integration, fewer unit, contract tests instead of E2E)

## Key Concepts
- **Unit Tests**: Test a single unit of code (function, class, module) in isolation. Fast (milliseconds), deterministic, no I/O. The foundation of the pyramid.
- **Integration Tests**: Test interactions between components — service + database, service + external API (using test doubles), multiple modules together. Slower than unit tests but faster than E2E.
- **End-to-End (E2E) Tests**: Test full user journeys through the running system — browser automation, API smoke tests. Slow, brittle, expensive to maintain. Use sparingly for critical paths.
- **Ice Cream Cone**: The anti-pattern — too many E2E tests, few unit tests. Slow CI, fragile tests, hard to diagnose failures.
- **Test Double**: Stubs, mocks, and fakes that replace real dependencies in unit tests to achieve isolation
- **Contract Tests**: An alternative to E2E for verifying service integrations in microservices — verify the contract between consumer and provider without a full integration environment
- **Testing Trophy**: Kent C. Dodds' variant that emphasizes integration tests over unit tests for UI-heavy systems — a valid alternative framing

## In Practice
Test Pyramid is the default test strategy framing at Method for all engagements. The target coverage distribution is context-dependent, but the principles are consistent: fast feedback loops require a unit test foundation; fragile pipelines are usually an ice cream cone diagnosis. In microservices, Contract Testing replaces many E2E tests — verifying service integrations without standing up the full system. The pyramid is introduced during NFR Requirements and operationalized in Code Generation.

## Engineering Knowledge
💡 **Engineering Knowledge — Test Pyramid**: Build your test suite like a pyramid: many fast unit tests at the base, a smaller layer of integration tests in the middle, very few slow E2E tests at the top. If your CI is slow and fragile, you've inverted the pyramid (ice cream cone). Unit tests catch logic bugs fast; integration tests catch wiring bugs; E2E tests confirm critical user journeys work. In microservices, contract tests replace most E2E tests. → `engineering-knowledge-repository/testing/test-pyramid.md`

## Related Entries
- [Test-Driven Development](test-driven-development.md) — TDD naturally builds the unit test base of the pyramid
- [Behavior-Driven Development](behavior-driven-development.md) — BDD scenarios often become integration or E2E tests
- [Contract Testing](contract-testing.md) — replaces E2E tests for service integration verification in microservices

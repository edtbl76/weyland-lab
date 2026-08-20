---
id: testing-strategies
tags: [methodology, testing, backend, frontend]
surfaces-at: [application-design, functional-design]
related: [ci-cd, frontend-testing, test-driven-development, contract-testing]
complexity: intermediate
---

# Testing Strategies

## What It Is
The overall approach to testing a software system — which tests to write, at which level of the stack, in what proportion, and how they fit into the development and deployment workflow. Testing strategy answers: what confidence level do we need, at what cost, and at what maintenance burden? Without an intentional strategy, teams default to writing too many narrow unit tests and too few integration tests — producing a test suite that passes when real bugs exist and fails when internal implementations change.

## When to Apply
- When starting a new project (establish strategy before accumulating tests)
- When a test suite is slow, brittle, or not providing confidence
- When writing tests feels more like a burden than a safety net
- When deciding which types of tests to require in the definition of done

## Key Concepts
- **Testing Pyramid** (Mike Cohn): The traditional model:
  - *Unit tests (bottom, many)*: Fast, isolated, cheap to write. Test individual functions or classes in isolation with mocked dependencies
  - *Integration tests (middle)*: Test interactions between components — service + database, controller + service. Use real dependencies where practical
  - *E2E tests (top, few)*: Test the full stack through the real UI. Slow, expensive to maintain, high confidence
  - Pyramid shape: many unit, fewer integration, very few E2E
- **Testing Trophy** (Kent C. Dodds): A revision of the pyramid more applicable to modern frontend and service testing:
  - *Static analysis (foundation)*: TypeScript, ESLint — zero runtime cost; catches type errors and anti-patterns
  - *Unit (small)*: Pure functions, utilities, isolated business logic
  - *Integration (large, most)*: Test a component or service through its real interface with realistic dependencies. Highest return on investment
  - *E2E (few)*: Critical user journeys only
  - Trophy shape favors integration tests over unit tests
- **Test Doubles**: Mechanisms for replacing dependencies in tests:
  - *Stub*: Returns fixed values; no behavior verification
  - *Mock*: Verifies that a dependency was called with expected arguments
  - *Fake*: A working implementation of a dependency (in-memory database, file system fake)
  - *Spy*: Wraps real implementation; records calls for verification
  - Rule: Prefer fakes over mocks; mocks couple tests to implementation details and break during refactors
- **Contract Testing**: Tests that verify a service's API matches the expectations of its consumers — without deploying both together. Pact is the standard tool. Catches integration failures before they reach staging. Especially valuable for microservices and public APIs. See [Contract Testing](contract-testing.md)
- **Test-Driven Development (TDD)**: Write the test before writing the implementation. Red (failing test) → Green (minimal passing code) → Refactor. TDD produces better-designed code and naturally high test coverage. See [Test-Driven Development](test-driven-development.md)
- **Property-Based Testing**: Instead of specific examples, define properties that should hold for all inputs (`all valid emails should pass validation`). The framework generates hundreds of random inputs and reports failures. Hypothesis (Python), fast-check (TypeScript)
- **Mutation Testing**: Automatically modify the source code (introduce bugs) and check whether tests catch the mutations. Measures test quality, not just coverage. Stryker (JavaScript), PITest (Java). High mutation score = tests actually catch bugs, not just execute code
- **Coverage as a Floor, Not a Ceiling**: Code coverage measures which lines were executed, not whether tests verified correct behavior. 80% coverage with meaningful assertions is better than 100% coverage that just calls functions without asserting results. Set coverage minimums (e.g., 80%) as a floor; don't treat 100% coverage as the goal

## In Practice
Method targets the testing trophy model. Integration tests constitute the majority of the test suite — service tests hit a real (test) database, not mocks. Unit tests cover pure business logic functions and utilities. Pact contract tests run in CI for service-to-service API compatibility. E2E tests with Playwright cover 3-5 critical user journeys per application. Coverage is measured but not enforced above 80%.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Testing Strategies**: More unit tests does not mean a better test suite. A unit test that mocks every dependency tests only that you called the mock — it cannot catch integration bugs. Favor integration tests that exercise realistic code paths over unit tests that mock everything. Test through the public interface of a module, not internal implementation details — implementation tests break on refactors that don't change behavior. E2E tests are valuable for critical journeys but expensive to maintain; keep the set small and focused. Contract tests are the highest-value test for catching breaking API changes between services. → `engineering-knowledge-repository/testing-strategies.md`

## Related Entries
- [CI/CD](ci-cd.md) — testing strategy determines which tests run at each CI stage
- [Frontend Testing](frontend-testing.md) — testing trophy model applied to React/Vue component and E2E testing
- [Test-Driven Development](test-driven-development.md) — TDD is a design methodology that naturally produces high-value tests
- [Contract Testing](contract-testing.md) — contract tests verify API compatibility between services without full integration deployment

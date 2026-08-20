---
id: test-doubles
tags: [pattern, testing]
surfaces-at: [code-generation]
related: [mutation-testing, property-based-testing, shift-left-testing, dependency-injection]
complexity: foundational
---

# Test Doubles

## What It Is
Replacement objects used in place of real dependencies during testing. Gerard Meszaros coined the term "test double" as the umbrella for all substitution types — mocks, stubs, fakes, spies, and dummies. Each type serves a different purpose and makes different guarantees. Understanding the distinctions prevents over-mocking and brittle tests.

## When to Apply
- Unit tests that need to isolate the class under test from slow, non-deterministic, or side-effecting dependencies (databases, external APIs, clocks)
- Tests that need to verify interactions (was a method called? with what arguments?)
- Simulating error conditions that are hard to reproduce with real dependencies

## When Not to Apply
- Integration and end-to-end tests — these should use real dependencies to verify actual behavior
- When the "real" dependency is fast, deterministic, and has no side effects — a test double adds complexity without benefit
- Over-mocking internal collaborators — if you're mocking everything, you're testing the mock, not the code

## Key Concepts
- **Dummy**: An object passed but never used — fills a required parameter. No behavior.
- **Stub**: Returns canned responses to calls. Used to supply indirect inputs to the system under test. Example: `when(repo.findById(1)).thenReturn(user)`
- **Fake**: A working implementation with simplified behavior — an in-memory database, a fake payment processor that always succeeds. More realistic than a stub.
- **Spy**: A real object that records calls for later verification — or a partial mock that delegates some calls to the real implementation
- **Mock**: An object pre-programmed with expectations about which calls it should receive. Fails the test if unexpected calls are made or expected calls are missing
- **Mockito (Java/Kotlin)**: The dominant mocking framework for JVM; `mock()`, `when()`, `verify()`
- **Jest Mocks**: `jest.fn()`, `jest.spyOn()` — built-in test double support in Jest
- **Test Against Interfaces**: Mock against abstractions (interfaces), not concrete classes — ensures tests don't break when implementation details change

## In Practice
Method's standard: stubs and fakes for dependencies that provide data; mocks for dependencies where the interaction (call count, arguments) is part of the behavior being tested. Avoid mocking domain objects — if you need to mock a value object, your design may have a problem. Use fakes for repositories in service-layer unit tests (faster, more realistic than mocks). Integration tests always use real dependencies.

## Engineering Knowledge
💡 **Engineering Knowledge — Test Doubles**: Know the taxonomy: Dummy (placeholder), Stub (canned return), Fake (working simplified implementation), Spy (records calls), Mock (pre-programmed expectations). Overuse of mocks leads to brittle tests that verify implementation not behavior. Use fakes for repositories in unit tests (in-memory implementation). Use mocks only when the *interaction itself* is the behavior being tested (e.g., "payment gateway was called once with correct amount"). Mock against interfaces, not concrete classes. → `engineering-knowledge-repository/testing/test-doubles.md`

## Related Entries
- [Mutation Testing](mutation-testing.md) — mutation testing depends on well-structured tests with meaningful assertions
- [Property-Based Testing](property-based-testing.md) — property-based tests often use stubs for external dependencies
- [Shift-Left Testing](shift-left-testing.md) — test doubles enable shift-left by making isolated unit testing fast

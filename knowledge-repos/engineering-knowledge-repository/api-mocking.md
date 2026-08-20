---
id: api-mocking
tags: [pattern, api-design, testing, backend]
surfaces-at: [functional-design, code-generation]
related: [openapi-specification, consumer-driven-contract-testing, test-doubles, api-first-design]
complexity: beginner
---

# API Mocking

## What It Is
Creating a simulated version of an API that returns realistic responses without executing real backend logic. Mock servers enable frontend development to proceed in parallel with backend development, allow testing against third-party APIs without incurring costs or rate limits, and provide stable test environments that don't depend on running services. API mocking is a natural extension of the API-first design approach — if the contract (OpenAPI spec) exists first, a mock server can be generated from it immediately.

## When to Apply
- Frontend and backend development in parallel — frontend needs an API before the backend is built
- Testing against third-party or external APIs (payment processors, external services) in CI/CD pipelines
- Demonstrating or prototyping functionality before backend implementation
- Isolating a service under test from its dependencies in integration tests

## Key Concepts
- **Contract-First Mocking**: Generate mock servers directly from OpenAPI specifications — Prism (Stoplight), WireMock, Mockoon. The spec is the source of truth; the mock server serves responses that conform to it
- **Static vs. Dynamic Responses**: Static mocks return fixed example responses. Dynamic mocks use request matching rules to return different responses based on request parameters — more realistic, required for testing different scenarios
- **Request Matching**: Match on HTTP method, path, query parameters, headers, and request body. Return different responses for different inputs — 200 for valid requests, 404 for unknown IDs, 422 for invalid input
- **Prism**: Generates a fully functional mock server from an OpenAPI spec with one command. Validates requests against the spec and returns example responses. The fastest path from spec to runnable mock
- **WireMock**: Flexible mock server with rich request matching and response templating. Supports recording real API interactions for replay. Strong Java ecosystem; also available standalone
- **Stateful Mocks**: Simulate state transitions — a POST creates a resource, the subsequent GET returns it. More complex to set up; required for testing multi-step workflows
- **Mock in CI, Real in Production**: Use mocks in CI pipelines for speed and stability; ensure integration tests against real services run in staging. Consumer-driven contract tests bridge the gap — they verify the real service matches the contract the mock was generated from
- **Avoid Mock Drift**: Mocks that diverge from the real API cause false-passing tests. Consumer-driven contract testing (Pact) keeps mocks honest

## In Practice
Method uses Prism for instant mock servers from OpenAPI specs during development. WireMock is used in integration test suites for third-party API dependencies. Consumer-driven contract tests (Pact) run in CI to validate that mock behavior matches the real service.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — API Mocking**: Generate your mock server from your OpenAPI spec — don't write mock responses by hand. Prism gives you a running mock in one command from a spec file. Pair mocking with consumer-driven contract tests to prevent mock drift — a mock that doesn't match the real API is worse than no mock (false confidence). Use dynamic mocks with request matching to test error scenarios, not just the happy path. Replace third-party API calls in CI with mocks — don't run integration tests against production external services. → `engineering-knowledge-repository/api-mocking.md`

## Related Entries
- [OpenAPI Specification](openapi-specification.md) — OpenAPI specs are the source of truth for generating mock servers
- [Consumer-Driven Contract Testing](consumer-driven-contract-testing.md) — contract tests validate that mocks match real service behavior
- [Test Doubles](test-doubles.md) — API mocks are a category of test double at the network boundary
- [API-First Design](api-first-design.md) — API-first enables immediate mock server generation before implementation

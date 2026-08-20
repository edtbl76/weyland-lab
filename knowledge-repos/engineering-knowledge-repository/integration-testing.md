---
id: integration-testing
tags: [methodology, testing, backend, frontend]
surfaces-at: [application-design, functional-design]
related: [testing-strategies, test-data-management, contract-testing, end-to-end-testing, ci-cd]
complexity: intermediate
---

# Integration Testing

## What It Is
Tests that verify the behavior of multiple components working together — a service and its database, a controller and its service layer, an API endpoint processing a real request through the full stack. Integration tests occupy the largest portion of the testing trophy (more valuable than unit tests; fewer than E2E) because they test real interactions between components without the fragility of full-stack E2E tests. A well-written integration test catches bugs that unit tests miss (the units work individually but not together) while running in seconds, not minutes.

## When to Apply
- API endpoints — test the full request/response cycle against a real database
- Service layer logic with real database queries and ORM behavior
- Message processing — consumers processing real messages from a real queue (or test double)
- Any code path where multiple components' interaction is the behavior under test

## Key Concepts
- **What Makes a Test "Integration"**: An integration test uses at least one real infrastructure dependency:
  - Real database (not mocked) — confirms SQL queries are correct, migrations are applied, ORM behavior is as expected
  - Real cache (Redis test instance) — confirms cache key patterns, TTLs, eviction behavior
  - Real message queue (SQS test, RabbitMQ test container)
  - The key insight: mocking the database in a "unit test" of an API endpoint means you're not testing whether the query actually works
- **Test Pyramid vs. Testing Trophy**: Unit tests are faster and cheaper per test; integration tests provide higher confidence per test. The testing trophy recommends investing more in integration tests than unit tests for most application code — the extra confidence (real database, real ORM, real SQL) is worth the slightly higher setup cost
- **Test Database**: Integration tests require a real database. Options:
  - *Test containers* (Testcontainers library): Spins up a real PostgreSQL/MySQL Docker container per test suite. The most reliable approach — real database, consistent environment, no shared state between runs
  - *In-memory SQLite*: Faster startup; but SQLite behavior diverges from PostgreSQL for complex queries, types, and features. Acceptable for simple CRUD; unreliable for production-like SQL
  - *Shared CI database*: A persistent database in CI. Requires careful cleanup to prevent test coupling
  - Recommendation: Testcontainers for PostgreSQL
- **HTTP Integration Tests**: Test API endpoints by making real HTTP requests through the framework's test client:
  - FastAPI: `TestClient(app)`
  - Django REST: `APIClient()`
  - Express: `supertest(app)`
  - These tests go through middleware, routing, serialization, and database — they test the full request/response cycle
- **Mocking External Services**: Integration tests should use real internal dependencies (database, cache) but mock external third-party services (payment processors, email providers, SMS APIs). This keeps tests fast and deterministic while testing real internal behavior. Mock at the HTTP level with MSW (frontend) or `responses` / `httpretty` (Python backend)
- **Test Speed**: Integration tests are slower than unit tests due to database I/O. Optimize by:
  - Running the database in Docker with tmpfs (in-memory filesystem) for faster I/O
  - Reusing the database connection pool across tests in the suite
  - Parallelizing tests across CPU cores (pytest-xdist, Jest --maxWorkers)
  - Transaction rollback per test (vs. truncation) for isolation without cost of full cleanup
- **Realistic Test Data**: Use factory-created data for each test. Avoid hardcoded fixture files that couple test data to specific record IDs or sequences. See [Test Data Management](test-data-management.md)

## In Practice
Method API services use FastAPI `TestClient` for HTTP integration tests against a PostgreSQL Testcontainer. Each test runs in a database transaction rolled back on teardown. External APIs are mocked with `responses`. Tests run in parallel via `pytest-xdist` with 4 workers. CI spins up a fresh PostgreSQL container per test run. Integration tests are the majority of the test suite (~60%); unit tests cover pure functions and business logic (~30%); E2E tests cover 3-5 critical flows (~10%).

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Integration Testing**: Test your API endpoints with a real database, not a mock — the most common bugs are SQL errors, ORM misconfiguration, and migration-code mismatch, none of which show up in tests with a mocked database. Testcontainers eliminates the "but it works differently in CI" problem by running a real PostgreSQL instance in Docker. Transaction rollback for test isolation is fast and reliable — each test gets a clean database state without the cost of truncation. Write more integration tests than unit tests; the testing trophy is right. → `engineering-knowledge-repository/integration-testing.md`

## Related Entries
- [Testing Strategies](testing-strategies.md) — integration testing occupies the largest category in the testing trophy model
- [Test Data Management](test-data-management.md) — factory-based test data and transaction rollback enable fast, isolated integration tests
- [Contract Testing](contract-testing.md) — contract tests are a specialized integration test that verify API compatibility between services
- [End-to-End Testing](end-to-end-testing.md) — E2E tests cover full user journeys; integration tests cover component interactions
- [CI/CD](ci-cd.md) — integration tests run against real dependencies in CI via Docker containers

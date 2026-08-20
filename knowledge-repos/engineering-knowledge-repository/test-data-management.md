---
id: test-data-management
tags: [methodology, testing, backend]
surfaces-at: [application-design, functional-design]
related: [testing-strategies, integration-testing, test-driven-development, database-migrations, local-development-environment]
complexity: intermediate
---

# Test Data Management

## What It Is
The practices for creating, maintaining, and managing the data required for automated tests — database records, fixture files, seed data, and test state. Good test data management makes tests readable, isolated, and maintainable. Poor test data management produces tests that share mutable state (causing flaky test failures), require careful ordering, or need a specific database state that's hard to reproduce. Test data is as important as test code — it deserves the same level of care.

## When to Apply
- Any test suite that touches a database or requires pre-existing records
- When tests are flaky due to shared mutable state
- When setting up test data requires complex, multi-step procedures
- When tests break because unrelated tests modified shared fixtures

## Key Concepts
- **Test Isolation**: Each test creates and destroys its own data. Tests that share mutable state fail unpredictably based on execution order. Isolation strategies:
  - *Transaction rollback*: Wrap each test in a database transaction; roll back after the test. Fast; leaves no test data. Used in Django, Rails, and SQLAlchemy test frameworks
  - *Truncation*: Delete all rows after each test. Slower than rollback but compatible with tests that commit transactions (Celery tasks, async operations)
  - *Test-specific schema*: Each test run uses a separate database schema (PostgreSQL schemas). Enables parallel test execution
- **Factory Pattern**: Define object factories that create valid, minimal records with sensible defaults and allow overriding specific fields:
  ```python
  # factory_boy (Python)
  user = UserFactory(email="test@example.com")  # other fields use defaults

  # factory_girl / FactoryBot (Ruby)
  create(:order, status: :pending)
  ```
  - Factories replace static fixtures: they create fresh data per test with explicit attributes, making tests self-documenting
  - Popular libraries: factory_boy (Python), FactoryBot (Ruby), factory (Go), faker.js (Node.js)
- **Fixtures**: Static data files (JSON, YAML, SQL) loaded before tests. Simpler to understand; hard to maintain as schema evolves; shared between tests causes coupling. Prefer factories for unit/integration tests; use fixtures for read-only reference data (enum values, static configuration)
- **Fake Data Generation**: Generate realistic but synthetic test data using faker libraries (Faker.js, Faker.py). `faker.email()`, `faker.name()`, `faker.address()`. Avoids hardcoded test strings like "test@test.com" while keeping tests readable
- **Seeding for Development and E2E**: A seed script populates the development database (and staging for E2E tests) with representative, stable data. Different from test factories — seed data is shared state for exploratory testing and E2E flows. Seed scripts should be idempotent (safe to run multiple times)
- **Test Database Setup**:
  - Use a dedicated test database — never run tests against production or staging databases
  - Run migrations before the test suite to keep the test schema current
  - For CI: spin up a fresh database container (PostgreSQL Docker image) per CI run. This is the most reliable isolation
- **Avoiding Hardcoded IDs**: Tests that rely on specific record IDs (`assert order.id == 42`) break when database sequences reset or records are inserted in different order. Always use the factory-created record's ID, not a hardcoded value
- **Builder Pattern for Complex State**: When tests require complex multi-entity state, use a builder or scenario helper:
  ```python
  scenario = CheckoutScenario.build(
      user=UserFactory(),
      cart_with_items=3,
      payment_method="card"
  )
  ```
  This is more readable than assembling 10 factories inline in each test

## In Practice
Method Python services use factory_boy for all test data creation. Tests use database transaction rollback for isolation — each test runs in a transaction that is rolled back on teardown. CI uses a PostgreSQL container per test run with migrations applied at startup. Seed scripts populate dev and staging for manual testing and E2E flows. Faker generates realistic data for names, emails, and addresses. Fixtures are only used for static reference data that never changes.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Test Data Management**: Flaky tests that fail based on execution order are almost always caused by shared mutable test data — switch to per-test factories with transaction rollback and the flakiness disappears. Factory pattern over fixtures: fixtures are static and couple tests to a specific database state; factories create fresh, minimal, explicit data per test. Never run tests against production data — use a dedicated test database with CI-managed lifecycle. Idempotent seed scripts are infrastructure: treat them with the same care as migration scripts. → `engineering-knowledge-repository/test-data-management.md`

## Related Entries
- [Testing Strategies](testing-strategies.md) — test data management is a prerequisite for effective integration testing
- [Integration Testing](integration-testing.md) — integration tests require realistic test data and database state
- [Test-Driven Development](test-driven-development.md) — TDD workflows benefit from fast, isolated factory-based test data setup
- [Database Migrations](database-migrations.md) — test database setup runs migrations to keep test schema current
- [Local Development Environment](local-development-environment.md) — seed scripts populate the local development database for exploratory testing

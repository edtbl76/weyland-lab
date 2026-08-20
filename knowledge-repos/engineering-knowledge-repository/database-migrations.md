---
id: database-migrations
tags: [pattern, database, backend, deployment]
surfaces-at: [functional-design, code-generation]
related: [schema-evolution, database-transactions, ci-cd, infrastructure-as-code]
complexity: intermediate
---

# Database Migrations

## What It Is
Versioned, incremental scripts that evolve a database schema over time — adding tables and columns, modifying types, adding indexes, and removing obsolete structures. Migrations are the mechanism for applying schema evolution in a controlled, reproducible, and reversible way. Every schema change is a migration script committed to version control alongside the application code that depends on it. Migration tools (Flyway, Liquibase, Alembic, Prisma Migrate) track which migrations have been applied and run only pending ones.

## When to Apply
- Every database schema change in a production system
- As part of the CI/CD pipeline — migrations run as part of deployment
- Any team-based project where multiple engineers modify the database schema

## Key Concepts
- **Version Control for Schema**: Migrations are numbered sequentially (V001, V002...) or timestamped. The migration history in the database matches the migration files in version control — the schema state is reproducible from scratch
- **Forward Migrations**: The `up` migration — applies the change. Required
- **Rollback Migrations**: The `down` migration — reverses the change. Optional but valuable for deployments that must be quickly reverted. Not all changes are easily reversible (dropping a column with data)
- **Non-Destructive Migrations**: Add before removing. Adding a column, creating an index, adding a table — safe to run while the application is live. Dropping a column or table — only safe after the application code no longer references it
- **Expand-and-Contract for Zero-Downtime**: For breaking changes: (1) expand — add the new column/table; (2) deploy code that handles both old and new schema; (3) migrate data; (4) contract — remove old column once all code is updated. Avoids downtime from schema locks
- **Migration Locking**: Running migrations concurrently during multi-instance deployments can cause conflicts. Most tools acquire a lock on a migrations table to ensure only one instance runs migrations at a time
- **Index Creation Without Locking**: In PostgreSQL, `CREATE INDEX` takes an `AccessShareLock` that blocks writes. `CREATE INDEX CONCURRENTLY` builds the index without locking — takes longer but safe for production tables
- **Tools**:
  - *Flyway*: Java-based; SQL or Java migrations; widely used in Spring/JVM ecosystems
  - *Liquibase*: XML/YAML/SQL migrations; rollback support; database-agnostic
  - *Alembic*: Python (SQLAlchemy); auto-generates migration scripts from model changes
  - *Prisma Migrate*: TypeScript/Node.js; generates migrations from Prisma schema changes
- **Test Migrations**: Run migrations in CI against a real database — not just against the ORM model. Catch migration syntax errors and data issues before production

## In Practice
Method uses Alembic for Python/PostgreSQL services and Flyway for Java services. Migrations run automatically at deployment before the new application code starts. `CREATE INDEX CONCURRENTLY` is used for all production index additions. Expand-and-contract is required for any column rename or type change. Migrations are reviewed in code review like application code.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Database Migrations**: Never modify a production database schema manually — every change is a versioned migration script committed to source control. Run migrations in CI against a real database — ORM model checks don't catch SQL syntax errors. Use `CREATE INDEX CONCURRENTLY` in PostgreSQL to avoid write locks during index creation. For breaking changes (rename, type change, drop), use expand-and-contract to maintain zero-downtime deployments. Ensure only one migration runner executes at a time during multi-instance deployments — most tools handle this with advisory locks. → `engineering-knowledge-repository/database-migrations.md`

## Related Entries
- [Schema Evolution](schema-evolution.md) — database migrations are the mechanism for applying schema evolution to relational databases
- [Database Transactions](database-transactions.md) — migrations run within transactions for atomicity — a failed migration rolls back completely
- [CI/CD](ci-cd.md) — migrations run as a pipeline stage before deploying new application code
- [Infrastructure as Code](infrastructure-as-code.md) — database migrations are the IaC equivalent for database schema state

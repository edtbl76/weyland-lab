---
id: schema-evolution
tags: [pattern, data, backend, api-design]
surfaces-at: [functional-design, application-design]
related: [data-serialization-formats, data-contracts, kafka, api-versioning, database-migrations, consumer-driven-contract-testing]
complexity: intermediate
---

# Schema Evolution

## What It Is
Managing changes to data schemas over time without breaking existing producers or consumers. As systems evolve, schemas must change — new fields are added, old fields become obsolete, types change. In distributed systems where producers and consumers are deployed independently, a schema change deployed to the producer must not break consumers still running the old code. Schema evolution is the discipline of making schema changes safely through compatibility rules and tooling.

## When to Apply
- Any schema used by multiple independent services or components
- Event schemas in Kafka topics consumed by multiple services
- API request/response schemas with multiple clients
- Database schemas with deployed applications reading them

## Key Concepts
- **Compatibility Types**:
  - *Backward compatible*: New schema can read data written by old schema. Consumers can be upgraded before producers. Safe: add optional fields with defaults; unsafe: remove fields, rename fields, change types
  - *Forward compatible*: Old schema can read data written by new schema. Producers can be upgraded before consumers. Safe: remove optional fields; unsafe: add required fields without defaults
  - *Full compatible*: Both backward and forward compatible. The safest approach for long-lived schemas
- **Breaking vs. Non-Breaking Changes**:
  - Non-breaking (safe): Add optional field with default, add new enum value, add new message type
  - Breaking (unsafe): Remove a field, rename a field, change a field's type, make an optional field required
- **Schema Registry**: A centralized service that stores schema versions and enforces compatibility rules before a new schema version is accepted. Confluent Schema Registry for Kafka — producers must register their schema; the registry rejects incompatible changes. Prevents accidental breaking changes from reaching consumers
- **Additive-Only Evolution**: The simplest strategy — only ever add new optional fields; never remove or rename. Fields that are no longer needed are deprecated and ignored, not removed. Enables indefinite backward compatibility
- **Field Deprecation**: Mark fields as deprecated in the schema before removing them. Give consumers a migration window (one or more release cycles). Remove only after all consumers have updated
- **Database Schema Migrations**: Tools (Flyway, Liquibase, Alembic) version and apply schema changes. Non-breaking migrations can be applied before deploying new code (expand). Breaking changes require expand-and-contract: add new structure, migrate data, deploy code, remove old structure
- **Expand-and-Contract Pattern**: For breaking database schema changes — (1) expand: add the new column/table alongside the old; (2) deploy code that writes to both and reads from new; (3) migrate data; (4) remove old column once all code is updated
- **Protobuf and Avro Evolution Rules**: Protobuf: never reuse field numbers; use `reserved` for removed fields. Avro: always provide default values for new fields to maintain backward compatibility

## In Practice
Method uses Confluent Schema Registry for all Kafka topics with backward compatibility enforcement. Database migrations use Alembic (Python) or Flyway (Java). All new fields in Kafka schemas have default values. Breaking database changes use the expand-and-contract pattern. Consumer-driven contract tests validate that producers don't break consumers.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Schema Evolution**: Design for backward compatibility from day one — add optional fields with defaults; never remove or rename fields without a deprecation window. Use a Schema Registry for Kafka to enforce compatibility rules automatically — it rejects incompatible schema changes before they reach consumers. For database schema changes, use expand-and-contract for breaking changes: add the new structure, migrate data while running both old and new code in parallel, then remove the old structure. Never reuse Protobuf field numbers. Always give consumers a migration window before removing deprecated fields. → `engineering-knowledge-repository/schema-evolution.md`

## Related Entries
- [Data Serialization Formats](data-serialization-formats.md) — format choice determines what evolution rules apply
- [Data Contracts](data-contracts.md) — data contracts formalize schema compatibility expectations between teams
- [Kafka](kafka.md) — Kafka topic schemas require careful evolution with Schema Registry enforcement
- [API Versioning](api-versioning.md) — API versioning is schema evolution applied to REST/GraphQL contracts
- [Database Migrations](database-migrations.md) — database migrations implement schema evolution for relational databases
- [Consumer-Driven Contract Testing](consumer-driven-contract-testing.md) — contract tests verify schema changes don't break consumers

---
id: data-contracts
tags: [pattern, data, backend]
surfaces-at: [application-design, functional-design]
related: [schema-evolution, data-quality, data-pipelines, consumer-driven-contract-testing, data-catalog, kafka]
complexity: intermediate
---

# Data Contracts

## What It Is
A formal, versioned agreement between a data producer and its consumers that defines the schema, semantics, quality expectations, SLAs, and ownership of a dataset. Data contracts make implicit assumptions explicit — they prevent producers from making breaking changes without consumer awareness, establish accountability for data quality, and provide consumers with reliable guarantees about the data they depend on. As data mesh and decentralized data ownership become prevalent, contracts are the interface between data teams.

## When to Apply
- When multiple downstream consumers depend on a data source owned by another team
- Before a data producer makes a schema change that could break consumers
- When establishing data quality SLAs between producer and consumer teams
- In data mesh architectures where domains publish data as products

## Key Concepts
- **Contract Contents**: Schema (field names, types, nullability), semantics (what the data means), quality expectations (null rates, freshness SLAs, row count ranges), ownership (who owns the data and is responsible for its quality), versioning policy, deprecation notice period
- **Schema as Code**: Define contracts as machine-readable schema files (Avro, JSON Schema, Protobuf, dbt model definitions) committed to version control. Contracts are not documents — they are enforced artifacts
- **Contract Testing**: Automated tests that validate the data conforms to the contract. Consumers write tests against the expected contract; producers run those tests before any schema change is deployed. Pact for service-to-service contracts; dbt tests for data warehouse contracts
- **Breaking Change Process**: A producer wanting to make a breaking schema change must notify consumers, provide a migration window (defined in the contract), and receive acknowledgment before proceeding. The contract formalizes this process
- **Data Product Thinking**: In data mesh architectures, datasets are treated as products — the producing team is the product owner, the contract is the API, and consumers are customers. Quality, discoverability, and contract compliance are the product's responsibility
- **Ownership and Accountability**: Contracts establish who to contact when data quality degrades. Without ownership, bad data has no responsible party. The contract names the owner and their SLA obligations
- **Tooling**: Data contract frameworks (datacontract.com spec, Soda Checks, Monte Carlo) provide standardized contract definition and monitoring. Schema Registry enforces schema contracts for Kafka. dbt exposures and sources document contracts within the warehouse
- **Contract Versioning**: Contracts are versioned. Minor versions: backward-compatible additions. Major versions: breaking changes with a migration window. Old major versions are supported for a defined sunset period

## In Practice
Method defines data contracts as YAML files co-located with the producing service or dbt project. Contracts specify schema, freshness SLA, quality thresholds, and owner. Consumer teams write contract tests that run in the producer's CI pipeline. Schema Registry enforces Kafka schema contracts automatically. Data quality alerts reference the contract to identify the responsible owner.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Contracts**: Data contracts make implicit promises explicit — formalize the schema, quality expectations, and SLAs that consumers actually depend on. Define contracts as versioned, machine-readable schema files, not wiki documents. Consumer teams should write contract tests that run in the producer's CI — breaking changes are caught before deployment. Name the owner in the contract: when data quality degrades, there must be a specific person responsible, not "the data team." In data mesh architectures, treat your dataset as a product and your contract as its API — consumers are customers with real expectations. → `engineering-knowledge-repository/data-contracts.md`

## Related Entries
- [Schema Evolution](schema-evolution.md) — data contracts define the compatibility rules and migration windows for schema evolution
- [Data Quality](data-quality.md) — data contracts formalize the quality expectations that data quality checks enforce
- [Data Pipelines](data-pipelines.md) — contracts govern the interfaces between pipeline stages and their consumers
- [Consumer-Driven Contract Testing](consumer-driven-contract-testing.md) — consumer-driven contract testing is the implementation mechanism for data contracts
- [Data Catalog](data-catalog.md) — data catalogs surface contract information for discoverability
- [Kafka](kafka.md) — Kafka Schema Registry enforces schema contracts for event stream consumers

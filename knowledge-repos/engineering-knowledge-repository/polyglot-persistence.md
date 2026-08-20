---
id: polyglot-persistence
tags: [principle, data, database]
surfaces-at: [functional-design, nfr-requirements, infrastructure-design]
related: [microservices, data-mesh, cqrs, event-sourcing]
complexity: intermediate
---

# Polyglot Persistence

## What It Is
The practice of using different data storage technologies for different parts of a system, selecting the database that best fits each use case rather than forcing all data into a single general-purpose database. A system might use a relational database for transactional records, a document store for flexible content, a graph database for relationship traversal, a search engine for full-text queries, and a cache for session state — each doing what it does best.

## When to Apply
- Microservices systems where each service owns its own data and can choose the right store
- Systems with genuinely heterogeneous data shapes and access patterns — relational, document, graph, time-series
- When a specific query pattern (full-text search, graph traversal, time-series aggregation) is poorly served by the primary relational database
- CQRS read models — the read side can use a different store (document, search) optimized for queries

## When Not to Apply
- Simple applications where a relational database handles all use cases adequately
- Small teams without the operational capacity to manage multiple database technologies
- When the marginal benefit of a specialized store doesn't justify the operational overhead and additional failure modes
- Early-stage products — optimize for simplicity, migrate to specialized stores when the need is proven

## Key Concepts
- **Fit-for-Purpose**: Each data store is chosen for its strengths — relational for ACID transactions, document for flexible schemas, graph for relationship queries, search for full-text, time-series for metrics
- **Service Data Isolation**: In microservices, polyglot persistence reinforces service boundaries — each service's data store is an implementation detail
- **Operational Overhead**: Each additional database technology adds backup, monitoring, version management, and developer expertise requirements
- **Data Consistency**: Cross-store queries or transactions are not possible — data that spans stores requires application-level coordination
- **Common Combinations**: PostgreSQL (transactions) + Redis (cache/session) + Elasticsearch (search) + S3 (blob storage) is a frequent stack in Method engagements

## In Practice
Polyglot persistence is a natural consequence of microservices — when each service owns its data, the appropriate store for each domain often differs. The most common entry point in Method engagements is adding search (Elasticsearch/OpenSearch) alongside a relational database for full-text query requirements, or Redis for caching hot read paths. The discipline is knowing when NOT to add another database — operational complexity grows with each addition and must be justified by concrete access pattern needs.

## Engineering Knowledge
💡 **Engineering Knowledge — Polyglot Persistence**: Not all data fits a relational table. Use the right database for each job: relational for transactions, document for flexible schemas, graph for relationships, search for full-text, time-series for metrics, cache for hot reads. Microservices make this natural — each service picks its own store. The discipline is restraint: every additional database technology adds ops overhead. Add a new store when a proven access pattern demands it, not speculatively. → `engineering-knowledge-repository/data/polyglot-persistence.md`

## Related Entries
- [Microservices](../architectural-styles/microservices.md) — service data isolation enables polyglot persistence
- [CQRS](../architectural-styles/cqrs.md) — CQRS read models are a common driver for polyglot persistence
- [Data Mesh](data-mesh.md) — domain data products may use different stores per domain

---
id: database-normalization
tags: [pattern, database, backend, data]
surfaces-at: [functional-design, application-design]
related: [olap-vs-oltp, database-transactions, database-indexing, polyglot-persistence, data-warehouse]
complexity: intermediate
---

# Database Normalization

## What It Is
The process of organizing a relational database schema to reduce data redundancy and improve data integrity by dividing data into related tables and defining relationships between them. Normalization applies a series of normal forms (1NF through BCNF and beyond) that progressively eliminate redundancy. Denormalization is the deliberate reversal — reintroducing redundancy for query performance. Both are valid design choices for different contexts: normalize for OLTP integrity; denormalize for OLAP query performance.

## When to Apply
- Designing OLTP database schemas where data integrity and write performance matter
- When update anomalies (updating the same data in multiple places) are a concern
- When evaluating tradeoffs between schema flexibility and query performance

## Key Concepts
- **First Normal Form (1NF)**: Each column contains atomic (indivisible) values; no repeating groups. No arrays or comma-separated values in a single column
- **Second Normal Form (2NF)**: 1NF + every non-key column depends on the entire primary key (not just part of it). Eliminates partial dependencies in composite-key tables
- **Third Normal Form (3NF)**: 2NF + no non-key column depends on another non-key column (no transitive dependencies). The standard target for OLTP schema design
- **Boyce-Codd Normal Form (BCNF)**: Stricter than 3NF — every determinant is a candidate key. Addresses edge cases 3NF misses; rarely necessary in practice
- **Update Anomalies**: The problems normalization prevents — insert anomaly (can't store data without other data), update anomaly (changing a value requires updating many rows), delete anomaly (deleting a row loses other information)
- **Denormalization**: Intentionally storing redundant data to improve read performance — precomputed aggregates, embedded foreign key data, materialized values. Common in OLAP schemas (star schema) and high-read OLTP tables where join cost is prohibitive
- **Star Schema**: The standard OLAP denormalized design — a central fact table with measure columns, surrounded by dimension tables with descriptive attributes. Optimized for analytical queries; violates 3NF by design
- **When to Denormalize in OLTP**: When join cost on critical read paths is measured to be a performance bottleneck. Denormalization introduces update complexity — any denormalized copy must be kept in sync. Use triggers or application-level logic carefully
- **JSON Columns**: Modern databases support JSON columns that embed structured data — a form of controlled denormalization. Useful for variable schemas but sacrifices referential integrity and query optimization

## In Practice
Method designs OLTP schemas to 3NF as the default. Denormalization is introduced only when query profiling reveals join costs that cannot be resolved by indexing. Data warehouse models (dbt) use star schema denormalization explicitly for analytical performance. JSON columns are used for genuinely variable schema attributes (metadata, configuration) but not as a general-purpose workaround for schema design.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Database Normalization**: Design OLTP schemas to 3NF — it eliminates update anomalies and maintains integrity without over-engineering. Denormalize only when profiling shows join costs are a real bottleneck, not preemptively. For analytical workloads (data warehouse), denormalization is deliberate and correct — star schema is the right design. JSON columns are useful for variable metadata but don't use them to avoid designing a proper relational schema. The tradeoff is always: normalization protects integrity and write performance; denormalization accelerates reads at the cost of write complexity. → `engineering-knowledge-repository/database-normalization.md`

## Related Entries
- [OLAP vs. OLTP](olap-vs-oltp.md) — normalization is standard for OLTP; denormalization (star schema) is standard for OLAP
- [Database Transactions](database-transactions.md) — normalized schemas reduce the scope of transactions needed to maintain consistency
- [Database Indexing](database-indexing.md) — proper indexing on normalized schemas reduces the join cost that tempts premature denormalization
- [Polyglot Persistence](polyglot-persistence.md) — choosing different database types for different workloads avoids normalization-vs-performance tradeoffs
- [Data Warehouse](data-warehouse.md) — data warehouse schemas deliberately denormalize using star schema for analytical performance

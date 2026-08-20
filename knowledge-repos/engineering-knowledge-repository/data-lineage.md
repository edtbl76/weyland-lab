---
id: data-lineage
tags: [methodology, data, backend]
surfaces-at: [application-design, infrastructure-design]
related: [data-catalog, data-pipelines, data-quality, data-warehouse, data-lake, data-contracts]
complexity: intermediate
---

# Data Lineage

## What It Is
The ability to track the origin, movement, transformation, and consumption of data throughout its lifecycle — from source system through pipelines, transformations, and storage, to the dashboards and models that consume it. Data lineage answers: where did this data come from? What transformed it? What depends on it? It is essential for debugging data quality issues (trace a bad metric back to its root cause), impact analysis (understand what breaks if a source schema changes), compliance (demonstrate where personal data flows), and trust (engineers and analysts need to know data provenance before relying on it).

## When to Apply
- Any multi-stage data pipeline where debugging data issues requires tracing back to the source
- Before making schema or pipeline changes — understand what downstream systems are affected
- Compliance and audit requirements (GDPR data flows, SOX financial data provenance)
- When implementing a data catalog — lineage is a core catalog capability

## Key Concepts
- **Column-Level Lineage**: Tracks not just which tables transform to which, but which specific columns are derived from which source columns. Fine-grained but expensive to compute. Essential for PII tracking and precise impact analysis
- **Table/Dataset-Level Lineage**: Tracks which datasets are inputs and outputs of each pipeline stage. Coarser but much easier to generate. The practical starting point
- **Lineage Capture Methods**:
  - *Static analysis*: Parse SQL and pipeline definitions to extract lineage without running them. dbt lineage, SQLLineage. Works at development time
  - *Runtime capture*: Capture lineage from actual pipeline execution. OpenLineage standard; Airflow, Spark, and dbt emit lineage events to Marquez or DataHub
- **OpenLineage**: An open standard for lineage metadata collection. Defines how pipeline tools (Airflow, Spark, dbt) emit lineage events in a common format. Backends: Marquez (open source), DataHub, Atlan
- **dbt Lineage**: dbt automatically generates a DAG showing model dependencies — which models are inputs to which. `dbt docs generate` produces an interactive lineage graph. The most accessible lineage tool for data warehouse teams
- **Impact Analysis**: Given a source schema change, lineage enables answering "what downstream models, dashboards, and ML features depend on this table?" Prevents silent breakage from upstream changes
- **Root Cause Analysis**: Given a data quality failure, lineage enables tracing backward — which transformation introduced the issue, which source data was the origin
- **Compliance Lineage**: For GDPR, demonstrate which systems receive personal data and trace data subject requests through the full data flow. Column-level lineage is required for precise PII tracking

## In Practice
Method uses dbt lineage for warehouse model dependency graphs. OpenLineage with Airflow and Spark emits runtime lineage to DataHub. PII column lineage is tracked explicitly for GDPR compliance reporting. Before any source schema change, DataHub lineage is queried to identify impacted downstream assets.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Lineage**: Lineage is the data debugging superpower — without it, tracing a wrong metric back to its root cause in a multi-stage pipeline is guesswork. Start with dbt lineage for warehouse models (free, auto-generated). Add OpenLineage to Airflow and Spark for runtime lineage across the full pipeline. Use lineage for impact analysis before schema changes — know what breaks before you change anything. For GDPR compliance, column-level PII lineage is not optional — you need to demonstrate where personal data flows and be able to execute subject deletion requests. → `engineering-knowledge-repository/data-lineage.md`

## Related Entries
- [Data Catalog](data-catalog.md) — lineage is surfaced through the data catalog for discoverability and impact analysis
- [Data Pipelines](data-pipelines.md) — lineage is captured from pipeline execution metadata
- [Data Quality](data-quality.md) — lineage enables root cause analysis when quality checks fail
- [Data Warehouse](data-warehouse.md) — dbt lineage provides model dependency graphs for warehouse transformations
- [Data Lake](data-lake.md) — lineage tracks data flow between lake zones and downstream consumers
- [Data Contracts](data-contracts.md) — lineage reveals the actual data flow that contracts should govern

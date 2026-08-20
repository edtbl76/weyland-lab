---
id: data-catalog
tags: [tooling, data, backend]
surfaces-at: [application-design, infrastructure-design]
related: [data-lake, data-warehouse, data-lineage, data-contracts, data-quality, data-mesh]
complexity: intermediate
---

# Data Catalog

## What It Is
A centralized metadata repository that makes data assets across an organization discoverable, understandable, and governable. A data catalog answers the questions engineers and analysts face daily: what datasets exist, what do they contain, where do they come from, who owns them, how fresh are they, and are they trustworthy? Without a catalog, data discovery is ad-hoc — people ask colleagues, search Slack, or stumble across datasets by accident. At scale, an undiscoverable dataset is an unused dataset.

## When to Apply
- When data assets span multiple teams and systems and discovery is becoming a bottleneck
- When implementing a data mesh architecture — catalog is foundational to data product discoverability
- When data governance, compliance, or audit requirements demand data asset documentation
- When analysts waste significant time finding and understanding data

## Key Concepts
- **Metadata Types**:
  - *Technical metadata*: Schema, data types, column descriptions, row counts, freshness, storage location
  - *Business metadata*: What the dataset means, business definitions, use cases, data owner, sensitivity classification
  - *Operational metadata*: Pipeline lineage, last updated, quality check results, SLA status
- **Automated Discovery**: Crawlers scan data sources (S3, Snowflake, Kafka, databases) and extract technical metadata automatically. AWS Glue Data Catalog, Google Data Catalog, Apache Atlas. Manual documentation doesn't scale — automation is required
- **Search and Discovery**: Full-text search across dataset names, descriptions, column names, and tags. Users should find datasets by business concept, not by knowing the exact table name
- **Data Lineage Integration**: Catalogs surface lineage — where data comes from, what transforms it, what depends on it. Lineage in the catalog enables impact analysis before schema changes
- **Data Quality Integration**: Surface quality check results and freshness status in the catalog. Analysts should see data quality health before choosing a dataset
- **Business Glossary**: Canonical definitions of business terms — "active user," "revenue," "conversion." Links glossary terms to the datasets and columns that implement them. Eliminates ambiguity when different teams define the same term differently
- **Access Control and PII Classification**: Tag columns with sensitivity classification (PII, PCI, confidential). Enforce access policies based on tags. The catalog is the governance layer for data access control
- **Popular Tools**: AWS Glue Data Catalog (AWS-native, automatic crawling), Amundsen (Lyft, open source), DataHub (LinkedIn, open source), Atlan, Alation, Collibra (enterprise). dbt docs generate a lightweight catalog for warehouse models

## In Practice
Method uses dbt docs as the catalog for data warehouse models (auto-generated from dbt model definitions). AWS Glue Data Catalog registers S3 and Redshift assets. DataHub is used for cross-system lineage and broader organizational data discovery. PII columns are tagged in the catalog and access-controlled via IAM.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Catalog**: A data catalog is foundational infrastructure, not a nice-to-have — without it, your data lake becomes a swamp and your data warehouse becomes a mystery. Automate metadata ingestion; manual documentation decays immediately. Surface data quality status and freshness in the catalog — analysts must know if a dataset is trustworthy before using it. Build a business glossary to eliminate the "what does active user mean?" conversation across every team. In data mesh, the catalog is how data products are discovered — it's the marketplace for your data. → `engineering-knowledge-repository/data-catalog.md`

## Related Entries
- [Data Lake](data-lake.md) — the catalog makes lake datasets discoverable and prevents data swamp conditions
- [Data Warehouse](data-warehouse.md) — dbt docs generate a lightweight catalog for warehouse models
- [Data Lineage](data-lineage.md) — lineage is surfaced through the catalog for impact analysis and root cause investigation
- [Data Contracts](data-contracts.md) — contracts are surfaced in the catalog as the interface definition for data products
- [Data Quality](data-quality.md) — quality check results and freshness SLA status are exposed through the catalog
- [Data Mesh](data-mesh.md) — the catalog is the discoverability layer enabling data product consumption across domains

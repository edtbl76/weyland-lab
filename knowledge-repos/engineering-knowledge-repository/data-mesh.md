---
id: data-mesh
tags: [methodology, data, distributed-systems]
surfaces-at: [infrastructure-design]
related: [domain-driven-design, event-driven-architecture]
complexity: advanced
---

# Data Mesh

## What It Is
A decentralized data architecture approach that treats data as a product, owned by the domain teams that produce it. Rather than a central data team owning all data pipelines, each domain owns its data end-to-end — including collection, transformation, quality, and serving. Coined by Zhamak Dehghani.

## When to Apply
- Large organizations with multiple domain teams producing data independently
- When a central data team has become a bottleneck for analytics and data products
- Systems with clear domain boundaries (DDD) that map naturally to data ownership
- When data quality accountability needs to move to the teams closest to the data

## When Not to Apply
- Small organizations or teams — the overhead of treating every dataset as a product is not justified
- Systems without clear domain boundaries
- Organizations without the engineering maturity to maintain data products as first-class artifacts
- When a centralized data warehouse or lake is working well and scaling adequately

## Key Concepts
- **Domain Ownership**: Each domain team owns its data products — not a central data engineering team
- **Data as a Product**: Data sets are treated with the same quality standards as software products — discoverable, addressable, trustworthy, self-describing, interoperable, secure
- **Self-Serve Data Infrastructure**: Platform teams provide tooling so domain teams can build and maintain data products without central bottlenecks
- **Federated Computational Governance**: Global standards (interoperability, security, compliance) enforced by policy, not by centralized control
- **Data Product**: A discrete dataset or API owned by a domain, meeting product quality standards

## In Practice
Data Mesh surfaces in Infrastructure Design when a system is part of a larger data ecosystem — especially in enterprise modernization engagements where the client has a central data team that is struggling to scale. It is not a technology pattern — it is an organizational and architectural pattern. Introducing Data Mesh requires both technical and organizational change. Surface it as a consideration, not a mandate.

## Engineering Knowledge
💡 **Engineering Knowledge — Data Mesh**: If your system produces data consumed by other domains, consider who owns the quality and accessibility of that data. Data Mesh shifts ownership to the producing domain — your team becomes responsible for your data as a product, not just as a byproduct of your service. → `engineering-knowledge-repository/data/data-mesh.md`

## Related Entries
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — domain boundaries in DDD map to Data Mesh domain ownership
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — events are a natural distribution mechanism for data products

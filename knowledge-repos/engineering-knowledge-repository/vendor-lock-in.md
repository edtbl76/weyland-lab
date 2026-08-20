---
id: vendor-lock-in
tags: [anti-pattern, infrastructure, cloud]
surfaces-at: [application-design]
related: [build-vs-buy, managed-services-tradeoffs, wardley-mapping, evolutionary-architecture, twelve-factor-app]
complexity: intermediate
---

# Vendor Lock-In

## What It Is
An anti-pattern where a system becomes so tightly coupled to a specific vendor's proprietary APIs, services, or data formats that migrating to an alternative becomes prohibitively expensive or time-consuming. Vendor lock-in is a natural consequence of using proprietary services — the more deeply a product embeds vendor-specific features, the more leverage the vendor has over pricing, terms, and roadmap. Vendor lock-in is not always bad (the tradeoff of leverage for productivity is often worth it), but it becomes an anti-pattern when the coupling was unintentional, when it prevents competitive price negotiation, or when the vendor's roadmap diverges from the business's needs.

## How to Recognize It
- Migrating away from a vendor would require rewriting significant portions of the application
- Pricing increases cannot be negotiated because the cost of switching exceeds the cost of staying
- Business decisions are constrained by what the vendor supports rather than what the business needs
- Application code directly calls vendor-specific APIs rather than abstraction layers
- Data is stored in proprietary formats or locked in the vendor's storage with no export mechanism

## Key Concepts
- **Types of Lock-In**:
  - *API lock-in*: Application code uses vendor-specific SDK calls (AWS-specific DynamoDB calls, proprietary SaaS APIs) that have no portable equivalent
  - *Data lock-in*: Data stored in proprietary formats or on vendor-controlled storage where export is expensive, slow, or incomplete (some SaaS vendors make data export difficult by design)
  - *Operational lock-in*: Operational processes and tooling built around a specific vendor's console, CLI, or monitoring tools
  - *Skill lock-in*: Team expertise concentrated in vendor-specific technology; switching requires retraining and hiring

- **Not All Lock-In Is Bad**: Using AWS S3 is some lock-in; but S3's reliability, ubiquity, and low cost make the tradeoff clearly worth it. The question is not "is there any lock-in?" but "is the lock-in commensurate with the value received?" Using a managed PostgreSQL service (RDS, Cloud SQL) has minimal lock-in; using a proprietary multi-model database to save vendor management work has high lock-in

- **Abstraction as Mitigation**: Isolate vendor-specific calls behind abstraction layers. Storage interface → implementation can be S3 or GCS. Notification service → implementation can be SNS or Twilio. This doesn't eliminate lock-in but reduces the blast radius of a migration to the adapter layer

- **Data Portability**: Ensure data can be exported in standard formats (CSV, JSON, Parquet) at any time. This is both a lock-in mitigation and a GDPR/compliance requirement. Never accept a SaaS contract without confirming data export capabilities

- **The Multi-Cloud Fallacy**: Building multi-cloud-compatible infrastructure as a general practice is expensive, complex, and rarely worth it. Multi-cloud for disaster recovery (failover to another cloud) and for specific capability access (best AI services span clouds) is legitimate. Multi-cloud to avoid lock-in produces accidental complexity — you build the lowest common denominator across clouds rather than using each cloud's best capabilities

- **Open Standards as Exit Ramps**: Using open standards (OpenTelemetry, S3-compatible APIs, PostgreSQL wire protocol, Kubernetes) reduces lock-in because tools that implement the standard are interchangeable. Prefer vendors who implement open standards over those who require proprietary agents and formats

## In Practice
Method architecture reviews evaluate lock-in risk for each major vendor dependency. High-value managed services (AWS RDS, S3, SQS) are accepted with awareness; lock-in is justified by operational savings. Proprietary SaaS APIs are wrapped in adapter interfaces rather than called directly from domain code. Data export capabilities are verified before recommending any SaaS vendor. Multi-cloud is not a goal; single-cloud with standard interfaces is the default posture.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Vendor Lock-In**: Lock-in is a spectrum, not a binary. S3 is some lock-in; a proprietary database with no migration path is deep lock-in. Evaluate each dependency: is the productivity/reliability value commensurate with the migration cost if you need to leave? The practical mitigations are: abstraction layers for high-lock-in APIs, data export verification before contract signing, and preference for vendors who implement open standards. Don't build multi-cloud infrastructure to avoid lock-in — it's a false economy that creates complexity. Choose your vendor relationships deliberately, then manage them actively rather than discovering the lock-in at contract renewal time. → `engineering-knowledge-repository/vendor-lock-in.md`

## Related Entries
- [Build vs. Buy](build-vs-buy.md) — vendor lock-in risk is a key factor in build-vs-buy decisions
- [Managed Services Tradeoffs](managed-services-tradeoffs.md) — managed services offer productivity at the cost of some lock-in; tradeoffs must be evaluated per service
- [Wardley Mapping](wardley-mapping.md) — Wardley Maps surface which components are commoditized (low lock-in risk) vs. proprietary (high lock-in risk)
- [Evolutionary Architecture](evolutionary-architecture.md) — evolutionary architecture uses fitness functions to detect when lock-in is growing beyond acceptable thresholds
- [Twelve-Factor App](twelve-factor-app.md) — twelve-factor principles (backing services as attached resources, config in environment) reduce infrastructure lock-in

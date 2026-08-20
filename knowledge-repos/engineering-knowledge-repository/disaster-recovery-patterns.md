---
id: disaster-recovery-patterns
tags: [reference, reliability, infrastructure, cloud]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [infrastructure-as-code, blue-green-deployment, auto-scaling, service-level-objectives]
complexity: intermediate
---

# Disaster Recovery Patterns

## What It Is
Strategies for recovering systems and data after a catastrophic failure — data center loss, region-wide outage, ransomware, accidental deletion. Disaster recovery is defined by two metrics: **RTO** (Recovery Time Objective — how long can the system be down?) and **RPO** (Recovery Point Objective — how much data can be lost?). Different strategies achieve different RTO/RPO tradeoffs at different costs.

## When to Apply
- All production systems with defined availability requirements
- Before the first production launch — DR is much easier to design upfront than retrofit
- For any system where downtime has significant business or regulatory consequences

## When Not to Apply
- Internal development and test environments
- Prototype systems with no business continuity requirements

## Key Concepts
**Four DR Strategies (increasing cost and decreasing recovery time):**

- **Backup and Restore**: The simplest strategy. Regular backups stored in durable object storage (S3). Recovery: restore from backup to new infrastructure. Lowest cost, highest RTO (hours to days). RPO = time since last backup.

- **Pilot Light**: A minimal version of the system runs in the recovery environment at all times — core infrastructure provisioned, data replicated, application not running. Recovery: scale up the pilot light environment. RTO: minutes to hours. Moderate cost.

- **Warm Standby**: A scaled-down but fully functional version of the system runs continuously in the recovery environment. Recovery: scale up to full capacity and cut over traffic. RTO: minutes. Higher cost.

- **Multi-Site Active/Active**: Full capacity runs in multiple regions simultaneously; traffic is split across all. Recovery: route all traffic to surviving region(s). Lowest RTO (seconds), highest cost. Requires active-active architecture.

- **RTO**: How long can the business tolerate downtime? Hours? Minutes? Seconds? This drives strategy choice.
- **RPO**: How much data loss is acceptable? 24 hours? 1 hour? Zero? This drives replication requirements.

## In Practice
Method recommends Backup-and-Restore as the minimum for all production systems, with Pilot Light for systems with SLO requirements that make multi-hour RTO unacceptable. Infrastructure as Code is the enabler — if infrastructure is fully defined in code, "recovery" is running `terraform apply` against the DR environment. Test DR recovery at least quarterly — untested DR plans fail when needed.

## Engineering Knowledge
💡 **Engineering Knowledge — Disaster Recovery Patterns**: Start with RTO and RPO. Backup-and-restore is cheap but takes hours. Pilot light is faster (minutes to hours) but costs more. Warm standby is faster still. Active-active is near-instant but architecturally complex and expensive. The key enabler: Infrastructure as Code — if everything is in code, recreating an environment is `terraform apply` away. Test your DR plan quarterly — the worst time to discover it doesn't work is during an actual disaster. → `engineering-knowledge-repository/cloud-patterns/disaster-recovery-patterns.md`

## Related Entries
- [Infrastructure as Code](../deployment/infrastructure-as-code.md) — IaC enables fast environment recreation for DR
- [Service Level Objectives](../observability/service-level-objectives.md) — SLOs define the availability requirements that drive DR strategy choice

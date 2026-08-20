---
id: production-readiness-checklist
tags: [methodology, reliability, team-practices]
surfaces-at: [application-design]
related: [site-reliability-engineering, health-checks, service-level-objectives, on-call-management, security-hardening, incident-management]
complexity: foundational
---

# Production Readiness Checklist

## What It Is
A standardized checklist that a service must pass before it is permitted to go to production — covering observability, reliability, security, operational runbook, performance baselines, and ownership. Production readiness reviews (PRRs) originated at Google's SRE practice and have been adopted broadly as a way to ensure new services meet baseline operational standards before they impact real users. The checklist encodes institutional knowledge about what causes production incidents and creates a forcing function for engineering teams to address operational concerns before launch rather than scrambling post-incident.

## When to Apply
- Every new service or application before it handles production traffic
- When a service adds a new critical capability (e.g., payment processing) that changes its operational profile
- When migrating a service between infrastructure environments (new cloud provider, new region)
- At the start of an engagement to establish what "production ready" means for the client organization

## Key Concepts
- **Core Categories**: A production readiness checklist typically covers:
  - *Observability*: Structured logging implemented; metrics emitted; distributed tracing configured; health check endpoints present; dashboards published
  - *Alerting*: SLO defined; alerts configured for SLO breach; alert runbooks written; alerts tested in staging
  - *On-Call*: Service registered in PagerDuty/OpsGenie; escalation policy configured; runbook written and accessible; team is trained on incident response
  - *Security*: Auth enforced on all endpoints; secrets managed via secrets manager (not environment variables); dependency vulnerability scan passing; OWASP checklist reviewed
  - *Reliability*: Circuit breakers configured for dependencies; graceful degradation for non-critical dependency failures; retry policies with backoff configured; load tested at expected traffic level
  - *Deployment*: Zero-downtime deployment mechanism in place; rollback procedure documented and tested; feature flags used for risky functionality
  - *Documentation*: Service README with architecture overview; API documentation published; data flow diagram current; known limitations documented
  - *Ownership*: Service registered in service catalog with team owner; CODEOWNERS configured; data classification documented
- **Production Readiness Review (PRR)**: Formal review process (often SRE-facilitated) where a service team demonstrates readiness against each checklist item before receiving SRE support and traffic approval. The PRR is a conversation, not just a checkbox — it surfaces implicit risks
- **Tiered Readiness**: Not all services have the same criticality. A lightweight internal tool doesn't need the same rigor as a payment processing service. Tiered checklists (Tier 1: mission-critical; Tier 2: business-important; Tier 3: best-effort) match requirements to risk
- **Living Document**: Checklists evolve as teams learn from incidents. Every post-mortem should produce a checklist item if the incident reveals a gap in the standard baseline
- **Blocking vs. Advisory**: Checklist items are categorized as blocking (service cannot launch without this) or advisory (recommended but not required). Keep the blocking list short — too many blocking items and teams start treating the checklist as bureaucracy

## In Practice
Method's production readiness checklist is included in the build-and-test stage of every engagement. The checklist is tiered by service criticality. Blocking items include: health check endpoints, SLO definition, on-call registration, and secrets management compliance. Advisory items include: load testing, chaos engineering experiments, and performance profiling. The checklist is reviewed in the sprint before go-live, not the day before.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Production Readiness Checklist**: The production readiness checklist is the difference between "it works in staging" and "we're confident in production." Every incident post-mortem adds an item to the list — runbooks, circuit breakers, alert tuning — because someone learned it the hard way. Keep the blocking list short enough to be credible (< 10 items); put the rest as advisory. Review the checklist in the sprint before launch, not the day before — checklist findings discovered 24 hours before go-live become pressure to skip them. → `engineering-knowledge-repository/production-readiness-checklist.md`

## Related Entries
- [Site Reliability Engineering](site-reliability-engineering.md) — PRRs originated in Google SRE practice; SREs often facilitate production readiness reviews
- [Health Checks](health-checks.md) — health check endpoints are a universal blocking item on every production readiness checklist
- [Service Level Objectives](service-level-objectives.md) — SLO definition is required before a service goes to production
- [On-Call Management](on-call-management.md) — on-call registration and runbook completion are blocking production readiness items
- [Security Hardening](security-hardening.md) — security baseline items (auth, secrets, vulnerability scan) are core checklist categories
- [Incident Management](incident-management.md) — incident response procedures must be in place before production traffic

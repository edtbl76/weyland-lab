---
id: service-level-objectives
tags: [methodology, observability, reliability]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [error-budgets, golden-signals, four-key-metrics, site-reliability-engineering, metrics-and-alerting]
complexity: intermediate
---

# Service Level Objectives (SLOs)

## What It Is
A target reliability level for a user-facing behavior, expressed as a percentage over a time window. SLOs are the operational contract between engineering and users. They're derived from Service Level Indicators (SLIs — the actual metrics) and inform Service Level Agreements (SLAs — the commercial commitments). An SLO might be: "99.9% of API requests complete successfully in under 200ms, measured over a rolling 30-day window."

## When to Apply
- Any production system that has users — internal or external
- Before production launch — define SLOs in NFR Requirements, not after an incident
- When prioritizing reliability work — use SLO breach history to direct engineering investment
- When communicating system health to product, business, or clients

## When Not to Apply
- Internal scripts and batch jobs where occasional failure is acceptable and no user impact occurs
- Prototype systems not yet serving real traffic

## Key Concepts
- **SLI (Service Level Indicator)**: The metric being measured — request success rate, latency percentile (p99), availability. The raw signal.
- **SLO (Service Level Objective)**: The target — "SLI ≥ 99.9% over 30 days." The internal reliability goal.
- **SLA (Service Level Agreement)**: The contractual commitment to customers — usually less ambitious than the SLO to allow buffer
- **Error Budget**: Derived from the SLO — 99.9% availability = 43.8 minutes/month of allowed downtime. The spending account for acceptable unreliability.
- **Alerting on SLO Burn Rate**: Alert when the error budget is being consumed faster than expected — not just when SLIs breach a threshold
- **Multi-Window Alerting**: Google SRE recommends alerting on error budget burn rate over a short window (1h) and a long window (6h) simultaneously — catches both fast burns and slow bleeds
- **User Journey SLOs**: Define SLOs on the user-visible behavior, not internal microservice health — an SLO on checkout success rate is more meaningful than one on payment-service uptime

## In Practice
SLO definition is Method's first infrastructure deliverable for any production engagement. The process: identify critical user journeys, define the SLI for each, set realistic targets based on current baseline + achievable improvement. SLOs drive the error budget, which drives the reliability vs. feature velocity conversation.

## Engineering Knowledge
💡 **Engineering Knowledge — Service Level Objectives**: Define what "working" means before you deploy. An SLO is a target reliability level — "99.9% of checkout requests succeed in under 500ms over 30 days." SLOs drive error budgets (how much unreliability you can spend), which make the reliability-vs-velocity tradeoff explicit and data-driven. Alert on error budget burn rate, not raw SLI breaches — burn rate catches degradations before they exhaust your budget. → `engineering-knowledge-repository/observability/service-level-objectives.md`

## Related Entries
- [Error Budgets](error-budgets.md) — the operational concept derived from SLOs
- [Golden Signals](golden-signals.md) — the four SLIs most relevant to user experience
- [Site Reliability Engineering](../methodologies/site-reliability-engineering.md) — SLOs are the foundation of SRE practice
- [Metrics and Alerting](metrics-and-alerting.md) — the implementation layer for SLO tracking

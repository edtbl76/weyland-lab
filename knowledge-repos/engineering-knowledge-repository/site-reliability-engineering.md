---
id: site-reliability-engineering
tags: [methodology, reliability, observability]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [four-key-metrics, service-level-objectives, chaos-engineering, blameless-postmortems]
complexity: intermediate
---

# Site Reliability Engineering (SRE)

## What It Is
A discipline that applies software engineering principles to operations and reliability problems. Originated at Google. SRE teams are software engineers who take on operational responsibilities — they automate toil, define and track reliability targets (SLOs), manage error budgets, and treat infrastructure as code. The core philosophy: if operations work is too manual and repetitive, automate it away.

## When to Apply
- Production systems with availability requirements that cannot be met through ad-hoc operational practices
- When "ops" and "dev" are separate teams creating a wall between development and production reliability
- When on-call engineers are overwhelmed with manual, repetitive work (toil) instead of improving systems
- Establishing reliability practices for a new product reaching production scale

## When Not to Apply
- Early-stage products not yet in production — SRE overhead isn't warranted before product-market fit
- Very small teams where the SRE separation creates overhead — embed reliability practices in engineering teams instead
- Systems with no reliability requirements (internal tooling, batch jobs) where downtime is acceptable

## Key Concepts
- **SLO (Service Level Objective)**: A target reliability level for a user-facing behavior — "99.9% of requests complete in < 200ms." The reliability contract with users.
- **SLI (Service Level Indicator)**: The metric that measures reliability — request success rate, latency percentile, error rate
- **Error Budget**: The allowable unreliability derived from the SLO — 99.9% availability = 43.8 minutes downtime/month budget. Used to balance reliability investment against feature velocity.
- **Toil**: Manual, repetitive, automatable operational work — SRE's mission is to eliminate it, keeping toil below 50% of time
- **Error Budget Policy**: When the error budget is exhausted, new features are paused until reliability is restored — the mechanism that aligns engineering and operations incentives
- **Blameless Culture**: Reliability incidents are treated as systemic failures to learn from, not individual failures to punish
- **Runbooks**: Documented procedures for common operational tasks — the starting point before automation

## In Practice
SRE practices are standard in Method infrastructure engagements for production-scale systems. The first deliverable is always SLO definition — what does reliability mean for this system, and who cares? Error budgets align product and engineering teams around the reliability investment decision. Toil reduction (automation) is the ongoing operational improvement work.

## Engineering Knowledge
💡 **Engineering Knowledge — Site Reliability Engineering**: SRE applies software engineering to operations — automate toil, define SLOs, track error budgets. The error budget is the key concept: 99.9% availability gives you 43.8 minutes of downtime per month to spend. When the budget runs out, new features pause until reliability is restored — this is what aligns product and engineering on reliability investment. Start with SLO definitions before anything else: what does "working" mean for this system? → `engineering-knowledge-repository/methodologies/site-reliability-engineering.md`

## Related Entries
- [Service Level Objectives](../observability/service-level-objectives.md) — SLOs are the core operational contract in SRE
- [Blameless Postmortems](../team-practices/blameless-postmortems.md) — the cultural practice that makes SRE learning effective
- [Chaos Engineering](../testing/chaos-engineering.md) — proactively validates the reliability SREs are responsible for
- [Four Key Metrics](../architectural-philosophy/four-key-metrics.md) — DORA metrics complement SRE's reliability metrics

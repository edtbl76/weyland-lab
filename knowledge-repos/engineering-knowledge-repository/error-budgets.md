---
id: error-budgets
tags: [methodology, observability, reliability]
surfaces-at: [nfr-requirements, requirements-analysis]
related: [service-level-objectives, four-key-metrics, site-reliability-engineering]
complexity: intermediate
---

# Error Budgets

## What It Is
The allowable amount of unreliability a service can have in a given period, derived directly from its SLO. If the SLO is 99.9% availability, the error budget is 0.1% — equivalent to 43.8 minutes of downtime per month. The error budget is the operational currency that balances reliability investment against feature velocity. When the budget is full, ship features. When the budget is depleted, pause features and invest in reliability.

## When to Apply
- Production systems with defined SLOs — the error budget is the direct operational consequence of the SLO
- When reliability and feature velocity decisions need to be made transparent and data-driven
- When product and engineering teams disagree on when to prioritize reliability work

## When Not to Apply
- Systems without SLOs — error budgets require an SLO to derive from
- Very low-traffic internal tools where reliability incidents don't have meaningful business impact

## Key Concepts
- **Error Budget Calculation**: (1 - SLO) × time window. 99.9% SLO over 30 days = 0.1% × 43,200 min = 43.2 minutes
- **Budget Spending**: Every minute of downtime, every SLO breach, every slow response spends from the error budget
- **Error Budget Policy**: The team's stated response when the budget is exhausted — "freeze non-critical deploys until reliability is restored" or "dedicate the next sprint to reliability work"
- **Budget Burn Rate**: How quickly the error budget is being consumed — a 2x burn rate means the budget will be exhausted in half the time window
- **Fast Burn / Slow Burn Alerts**: Alert when budget is being burned too fast (short-window) or steadily (long-window) — catches both sharp incidents and slow degradation
- **Reliability vs. Velocity Lever**: The error budget makes the tradeoff explicit. A team with budget remaining can accept more deployment risk. A team with depleted budget must invest in reliability before shipping more features.

## In Practice
Error budgets are the mechanism that makes SRE self-regulating — they align product and engineering incentives without requiring management intervention for every reliability decision. In Method engagements, establish the error budget policy in the same conversation as the SLO definition. Make it visible: post the current budget consumption on the team dashboard.

## Engineering Knowledge
💡 **Engineering Knowledge — Error Budgets**: 99.9% SLO = 43 minutes of downtime budget per month. When it's full, ship features. When it's depleted, stop and fix reliability. The error budget converts the abstract reliability vs. velocity tension into a concrete, data-driven decision. Set an error budget policy in writing — what the team does when the budget runs out — before you need it. Alert on burn rate, not just absolute exhaustion. → `engineering-knowledge-repository/observability/error-budgets.md`

## Related Entries
- [Service Level Objectives](service-level-objectives.md) — SLOs define the error budget
- [Site Reliability Engineering](../methodologies/site-reliability-engineering.md) — error budgets are the operational mechanism of SRE
- [Four Key Metrics](../architectural-philosophy/four-key-metrics.md) — deployment frequency and change failure rate directly affect error budget consumption

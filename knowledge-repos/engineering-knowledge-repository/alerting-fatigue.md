---
id: alerting-fatigue
tags: [anti-pattern, observability]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [metrics-and-alerting, service-level-objectives, on-call-practices, golden-signals]
complexity: foundational
---

# Alerting Fatigue

## What It Is
The anti-pattern where an on-call team receives so many alerts that engineers begin to ignore them — including real, critical incidents. When alerts fire constantly for non-urgent conditions, the team becomes desensitized. Alert fatigue is a leading cause of missed incidents, delayed responses, and burned-out on-call engineers. The fix is not more alerting infrastructure — it's fewer, higher-quality alerts.

## When to Apply (How to Recognize and Address)
- When on-call engineers are frequently silencing or acknowledging alerts without investigating
- When the same alert fires multiple times per shift for conditions that self-resolve
- When critical incidents are missed because they're indistinguishable from the constant alert noise
- When on-call is considered a burden rather than an engineering responsibility

## Key Concepts
- **Alert Signal-to-Noise Ratio**: The ratio of actionable alerts to noise alerts — high signal, low noise is the goal
- **Actionable Alert**: Every alert should require a specific, documented action — if the only action is "wait and see," it's not an alert; it's a notification
- **SLO-Based Alerting**: Alert on error budget burn rate — "your SLO is being violated" is always actionable. Alert on individual errors — often isn't.
- **Runbook Requirement**: Every alert should have a linked runbook. Alerts without runbooks cause hesitation and inconsistent responses.
- **Alert Routing by Severity**: P1 (wake someone up), P2 (urgent business hours), P3 (next sprint ticket). Not all alerts should page on-call at 3am.
- **Alert Review Cadence**: Regularly review alert history — delete alerts that fired many times without action, fix thresholds that are too sensitive
- **Toil Elimination**: Alerts that fire routinely for conditions the team manually resolves are toil — automate the response or fix the underlying cause

## In Practice
Alert audit is a standard Method recommendation in SRE engagements. Review the last 30 days of alert history: how many alerts required real action vs. were silenced? For each noisy alert, the answer is one of: fix the threshold, automate the response, or delete the alert. Aim for on-call shifts where alert volume is low enough that every page gets full attention.

## Engineering Knowledge
💡 **Engineering Knowledge — Alerting Fatigue**: Too many alerts is as dangerous as too few — engineers stop responding. Every alert must be actionable, linked to a runbook, and routed at the right severity. SLO-based alerting (burn rate) naturally produces fewer, more meaningful alerts than raw threshold alerts. Do a monthly alert audit: any alert that fired 10 times last month without requiring real action is either a false positive to fix or a problem to automate away. → `engineering-knowledge-repository/observability/alerting-fatigue.md`

## Related Entries
- [Metrics and Alerting](metrics-and-alerting.md) — alerting fatigue is the failure mode of poorly designed metric alerting
- [Service Level Objectives](service-level-objectives.md) — SLO-based alerting reduces noise by focusing on what matters to users
- [On-Call Practices](../team-practices/on-call-practices.md) — alerting fatigue directly impacts on-call quality and team wellbeing

---
id: four-key-metrics
tags: [reference, methodology, team-practices]
surfaces-at: [requirements-analysis, nfr-requirements]
related: [continuous-delivery, site-reliability-engineering, evolutionary-architecture]
complexity: foundational
---

# Four Key Metrics (DORA Metrics)

## What It Is
Four metrics identified by the DORA (DevOps Research and Assessment) research program as the strongest predictors of software delivery performance and organizational success. Published in the book *Accelerate* by Nicole Forsgren, Jez Humble, and Gene Kim. The metrics are: **Deployment Frequency**, **Lead Time for Changes**, **Change Failure Rate**, and **Mean Time to Restore (MTTR)**. High performers excel in all four simultaneously.

## When to Apply
- Establishing baseline engineering performance at engagement start
- Setting improvement goals for delivery transformation engagements
- Evaluating whether a new process, tool, or practice has improved delivery outcomes
- Reporting engineering health to leadership and stakeholders

## When Not to Apply
- Do not use the metrics as individual performance targets — they measure team and system health, not individual output
- Don't optimize one metric at the expense of others (e.g., increasing deployment frequency by skipping tests)
- Don't treat benchmarks as prescriptive targets — the goal is continuous improvement from your current baseline

## Key Concepts
- **Deployment Frequency**: How often the organization deploys code to production. Elite: on demand (multiple per day). The signal: teams that deploy more frequently have smaller, safer changes.
- **Lead Time for Changes**: Time from code committed to running in production. Elite: less than one hour. The signal: long lead time indicates large batches, slow pipelines, or heavy approval gates.
- **Change Failure Rate**: Percentage of deployments that cause a production incident requiring remediation. Elite: 0-15%. The signal: high failure rate indicates insufficient testing, poor observability, or risky deployment practices.
- **Mean Time to Restore (MTTR)**: How long to recover from a production failure. Elite: less than one hour. The signal: long MTTR indicates poor observability, complex rollback procedures, or weak on-call practices.
- **Stability vs. Throughput**: Classical thinking assumes speed and stability trade off. DORA research disproves this — high performers achieve both simultaneously.

## In Practice
DORA metrics are Method's recommended starting framework for engineering effectiveness measurement on delivery engagements. Establish baseline measurements in Iteration 0; track against them at each iteration. The most actionable metric for most teams is Lead Time — reducing batch size and improving pipeline automation directly moves it. MTTR is the best health indicator for production systems.

## Engineering Knowledge
💡 **Engineering Knowledge — Four Key Metrics (DORA)**: Deployment frequency, lead time, change failure rate, and MTTR are the four metrics that best predict engineering delivery performance. High performers excel at all four — speed and stability are not in conflict. Measure your baseline in Iteration 0. The most actionable lever is usually lead time: smaller batches, faster pipelines, fewer approval gates. Don't use these as individual performance scorecards — they measure systems and teams. → `engineering-knowledge-repository/architectural-philosophy/four-key-metrics.md`

## Related Entries
- [Continuous Delivery](../deployment/continuous-delivery.md) — CD directly improves deployment frequency and lead time
- [Site Reliability Engineering](../methodologies/site-reliability-engineering.md) — SRE practices directly improve MTTR and change failure rate

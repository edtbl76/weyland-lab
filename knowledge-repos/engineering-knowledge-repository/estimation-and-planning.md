---
id: estimation-and-planning
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [agile-practices, shape-up, four-key-metrics, working-agreements, technical-debt-management]
complexity: foundational
---

# Estimation and Planning

## What It Is
The practices for sizing and scheduling software work — determining how long tasks will take, how much work fits in a sprint or release, and how to communicate delivery timelines to stakeholders. Estimation is notoriously difficult in software; estimates are consistently optimistic. The goal is not perfect accuracy but calibrated uncertainty: knowing what is small vs. large, what is certain vs. risky, and how to communicate confidence levels honestly. Planning practices that acknowledge uncertainty — using ranges, tracking velocity, and planning in iterations — outperform those that demand false precision.

## When to Apply
- Sprint planning and backlog sizing
- Stakeholder requests for delivery timelines
- When scoping projects and determining what fits in a given time period
- When a team's actual delivery consistently diverges from planned delivery

## Key Concepts
- **Story Points vs. Time Estimates**:
  - *Story points*: Abstract units representing relative complexity — a 5-point story is roughly twice as complex as a 3-point story. Teams estimate in points, then measure velocity (points/sprint). Useful because teams are better at relative sizing than absolute time
  - *Time estimates*: Direct hours or days. More intuitive for non-engineering stakeholders; more susceptible to anchoring bias and overtime pressure
  - The distinction matters less than consistency: use whichever unit the team estimates accurately and consistently
- **Estimation Techniques**:
  - *Planning Poker*: Team members independently select estimate cards; reveal simultaneously; discuss disagreements. Reduces anchoring; surfaces hidden complexity. Most common Scrum estimation method
  - *T-Shirt Sizing* (XS/S/M/L/XL): Rough-cut sizing for roadmap planning and backlog grooming. Not used for sprint planning. Good for "is this a 1-week thing or a 3-month thing?" conversations
  - *Bucket System / Affinity Mapping*: Group user stories into complexity buckets (1, 2, 3, 5, 8, 13) by comparing them to each other. Fast for sizing large backlogs
  - *#NoEstimates*: Track cycle time for similar items rather than estimating each new item. Use historical data to forecast completion. Better for Kanban teams with predictable work types
- **Common Estimation Traps**:
  - *Optimism bias*: Estimates assume everything goes right. Apply a 1.5-2x multiplier for integration, review, testing, and unexpected complexity
  - *Estimate as commitment*: Estimates are predictions, not promises. A changing estimate is not a failure — it's updated information
  - *Anchoring*: Don't share your estimate before others reveal theirs. Planning poker's simultaneous reveal prevents this
  - *Forgetting non-feature work*: Estimates often omit code review time, test writing, deployment, documentation, and meetings. Budget for overhead (typically 20-30% of sprint capacity)
- **Velocity and Forecasting**:
  - Velocity: average story points completed per sprint over the last 3-6 sprints. Use to plan realistic sprint commitments
  - Use velocity ranges (min/average/max) not single numbers for sprint planning — it signals uncertainty
  - For release forecasting: "at average velocity, we will complete X features in Y sprints. At minimum velocity, it will take Z sprints."
- **Deadline Management**: When stakeholders need a date:
  1. Scope the work (what is the minimum viable version?)
  2. Estimate with appropriate uncertainty (this is a range, not a commitment)
  3. Identify risks that could change the estimate
  4. Agree on what will be dropped if the deadline is fixed (scope, not schedule, flexes)
  - "We can ship by date X if we scope to Y. If you add Z to scope, we can't hit X."
- **Spikes**: A time-boxed exploration to reduce uncertainty on a poorly understood item. Run a spike (1-2 days) to answer "how hard is this?" before estimating it. Spikes are common for unfamiliar technologies, unclear API integrations, or ambiguous requirements

## In Practice
Method uses planning poker with Fibonacci points (1, 2, 3, 5, 8, 13, 21). Items ≥ 8 points are split before sprint planning. T-shirt sizing is used for roadmap planning with clients (quarters out). Velocity is tracked in Jira over 6-sprint rolling windows. Sprint commitments use 80% of average velocity to maintain buffer for unexpected work. Release forecasts are communicated as ranges with explicit risk factors.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Estimation and Planning**: Software estimates are always wrong; the goal is calibrated uncertainty, not precision. Use relative sizing (story points) and velocity tracking to forecast realistically rather than committing to calendar dates based on optimistic task lists. Split large stories — any story > 1 sprint is hiding complexity that estimation cannot surface. When asked "when will it be done?", resist the single date; give a range based on velocity and explicitly name the risks that could push you to the longer end. The most dangerous estimation trap is treating an estimate as a commitment — it converts useful uncertainty information into performance pressure that produces shortcuts. → `engineering-knowledge-repository/estimation-and-planning.md`

## Related Entries
- [Agile Practices](agile-practices.md) — estimation is part of Scrum sprint planning; velocity is tracked per sprint
- [Shape Up](shape-up.md) — Shape Up explicitly rejects estimates in favor of fixed time budgets (appetites)
- [Four Key Metrics](four-key-metrics.md) — DORA metrics measure actual delivery performance independently of estimates
- [Working Agreements](working-agreements.md) — estimation approach (points vs. time, technique) is a team working agreement
- [Technical Debt Management](technical-debt-management.md) — technical debt affects estimation accuracy; untracked debt inflates estimates unpredictably

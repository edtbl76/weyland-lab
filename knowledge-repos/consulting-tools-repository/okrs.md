---
id: okrs
tags: [product, organizational, delivery]
surfaces-at: [validated-intent, requirements-analysis, workflow-planning]
related: [north-star-metric, rice-scoring, opportunity-solution-tree, raci, dependency-mapping]
complexity: foundational
---

# OKRs (Objectives and Key Results)

## What It Is
A goal-setting framework developed at Intel by Andy Grove and popularized by Google that structures organizational goals into Objectives (qualitative, aspirational, directional) and Key Results (quantitative, measurable, time-bound outcomes that indicate progress toward the Objective). OKRs separate direction (the Objective) from measurement (the Key Results), making goals both motivating and trackable. The framework operates at multiple levels — company, team, and individual — and typically runs on quarterly and annual cycles. OKRs are outcome-oriented, not output-oriented: Key Results measure what changed, not what was shipped.

## When to Use
- Aligning technology programs to business outcomes before scoping delivery
- When a client measures team success by output (features shipped, story points) rather than outcome (user adoption, revenue impact)
- Establishing success criteria for a program of work that can be tracked objectively
- Quarterly planning: determining which product investments map to current Objectives
- Program governance: tracking whether delivery is producing the expected key results

## Key Concepts
- **Objective**: Qualitative, directional, and inspiring — tells the team what they're aiming for. Should be achievable within the OKR cycle but ambitious enough to require real effort. Bad Objective: "Improve the platform." Good Objective: "Become the most trusted data platform for enterprise finance teams"
- **Key Results**: 3-5 measurable outcomes per Objective that demonstrate progress. Each KR should have a baseline, a target, and a metric. Bad KR: "Launch the new dashboard." Good KR: "Increase daily active users of reporting features from 200 to 800 by Q3"
- **Stretch Goals**: Google's OKR culture targets 70% achievement on Key Results — treating 100% as a signal that the goal wasn't ambitious enough. Not all organizations adopt this; calibrate to client culture
- **Output vs. Outcome**: The most common OKR failure is writing Key Results that describe outputs (shipped a feature) rather than outcomes (users adopted the feature). Outputs are within the team's control; outcomes are what the business actually cares about
- **OKR Hierarchy**: Company OKRs cascade to team OKRs, which cascade to individual OKRs. Alignment requires each level's Objectives to connect visibly to the level above. Disconnected OKRs at team level signal strategy misalignment
- **Check-ins**: OKRs require weekly or biweekly confidence scoring — not just end-of-quarter measurement. Confidence tracks whether the team believes the KR is achievable; a declining confidence score is an early warning signal
- **OKRs vs. KPIs**: KPIs measure ongoing operational health (always-on metrics); OKRs measure time-bounded change (what are we improving this quarter). Both are needed; conflating them produces cluttered goal frameworks

## Method Application
Method uses OKRs at the start of engagements to establish outcome-based success criteria before delivery begins. Technology programs without OKR-linked success criteria tend to measure success by delivery completion rather than business impact. OKRs also provide the governance framework for program reviews: each review starts with Key Result progress, not feature completion status.

## Consulting Insight
🎯 **Consulting Tool — OKRs**: The most impactful OKR intervention is rewriting a client's Key Results from outputs to outcomes. When a team writes "deliver the customer portal by June," replace it with "increase self-service resolution rate from 20% to 60% by June." The output may be necessary but it's not the goal — the outcome is. This reframe changes what the team optimizes for during delivery, not just what they report at the end. → `consulting-tools-repository/okrs.md`

## Related Entries
- [North Star Metric](north-star-metric.md) — the North Star is the single top-level metric that company OKRs should connect to
- [RICE Scoring](rice-scoring.md) — RICE scores should reflect OKR alignment; initiatives that don't move a current Objective warrant lower priority
- [Opportunity Solution Tree](opportunity-solution-tree.md) — OST structures the path from Objective to solution; Key Results map to Opportunity nodes
- [RACI](raci.md) — OKR ownership requires clarity on who is responsible and accountable for each KR
- [Dependency Mapping](dependency-mapping.md) — OKRs with cross-team Key Results require dependency mapping to manage shared commitments

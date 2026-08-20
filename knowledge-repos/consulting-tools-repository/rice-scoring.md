---
id: rice-scoring
tags: [product, delivery]
surfaces-at: [requirements-analysis, workflow-planning]
related: [moscow-prioritization, kano-model, north-star-metric, opportunity-solution-tree, decision-matrix]
complexity: foundational
---

# RICE Scoring

## What It Is
A quantitative prioritization framework that scores product initiatives or features across four dimensions: Reach, Impact, Confidence, and Effort. Developed at Intercom to reduce the influence of HiPPO (Highest Paid Person's Opinion) in product prioritization decisions. RICE produces a numeric score for each item — RICE Score = (Reach × Impact × Confidence) / Effort — allowing teams to rank a backlog by expected return on investment rather than stakeholder pressure or recency bias. The framework is deliberately simple: each dimension maps to a question teams can estimate with available data.

## When to Use
- Prioritizing a product backlog when multiple initiatives compete for limited engineering capacity
- Creating a defensible, data-informed roadmap to present to stakeholders
- When prioritization debates become political rather than analytical
- Quarterly planning: ranking initiatives before capacity allocation
- Evaluating whether a feature request should be pulled into a sprint based on expected return

## Key Concepts
- **Reach**: How many users or customers will this initiative affect in a given time period? Expressed as a number of people (not percentage). Forces teams to estimate actual user impact rather than vague "high reach" claims
- **Impact**: How much will this initiative move the needle for each user it reaches? Scored on a scale: 3 = massive, 2 = high, 1 = medium, 0.5 = low, 0.25 = minimal. The non-linear scale prevents compression at the high end
- **Confidence**: How confident is the team in the Reach and Impact estimates? Expressed as a percentage: 100% = high confidence, 80% = medium, 50% = low. Penalizes initiatives that sound compelling but lack supporting data
- **Effort**: How many person-months will this initiative require? Includes product, design, and engineering. The denominator — dividing by effort converts the numerator from output to ROI
- **RICE Score Formula**: (Reach × Impact × Confidence%) / Effort. Higher score = higher priority
- **Relative Scoring**: RICE scores are only meaningful relative to each other in the same context. A score of 40 is not inherently good or bad — it's only actionable when compared to a score of 8 or 200 in the same backlog
- **Limitations**: RICE works best for independent items with estimable reach data. It struggles with strategic initiatives (brand investment, platform foundations) where impact doesn't manifest as direct user reach, and with items that have hard dependencies
- **RICE vs. Story Points**: RICE scores prioritize what to build; story points estimate how long to build it. They operate at different levels and both are needed

## Method Application
Used in product roadmap workshops to replace subjective debates with structured estimation. When a client says "we need everything by Q3," RICE scoring forces a conversation about what "everything" produces vs. what the top-10 highest-RICE items produce — often 80% of the expected impact from 40% of the effort.

## Consulting Insight
🎯 **Consulting Tool — RICE Scoring**: RICE's value is not in the math — it's in making implicit assumptions explicit. When a team is forced to estimate Reach, Impact, and Confidence separately, disagreements surface immediately: one person thinks an initiative reaches 50,000 users; another thinks 500. That disagreement was always present; RICE makes it visible and resolvable. The Confidence multiplier is the most important column: it penalizes "sounds great in theory" initiatives and rewards evidence-backed ones. → `consulting-tools-repository/rice-scoring.md`

## Related Entries
- [MoSCoW Prioritization](moscow-prioritization.md) — tier-based prioritization; RICE scores can rank items within a MoSCoW tier
- [Kano Model](kano-model.md) — Kano classification informs RICE Impact estimates; Excitement features typically score higher on Impact
- [North Star Metric](north-star-metric.md) — RICE Reach and Impact should connect to North Star movement; items that don't affect the North Star warrant low Impact scores
- [Opportunity Solution Tree](opportunity-solution-tree.md) — OST structures which opportunities to score with RICE
- [Decision Matrix](decision-matrix.md) — alternative scoring approach for decisions with non-quantitative dimensions

---
id: moscow-prioritization
tags: [product, delivery]
surfaces-at: [requirements-analysis, workflow-planning, validated-intent]
related: [rice-scoring, kano-model, iron-triangle, dependency-mapping, decision-matrix]
complexity: foundational
---

# MoSCoW Prioritization

## What It Is
A requirements prioritization technique that categorizes requirements into four buckets: Must Have, Should Have, Could Have, and Won't Have (this time). Developed by Dai Clegg for use in RAD (Rapid Application Development) and later adopted widely in agile methodologies. MoSCoW provides a shared language for scope conversations between product, engineering, and stakeholders — making explicit what is in scope for a given release, what is deferred, and what has been consciously excluded. The "Won't Have" category is as important as the others: it documents the scope boundaries that prevent scope creep.

## When to Use
- Scoping a release or sprint when the team has more requirements than capacity
- Aligning stakeholders on scope before a delivery commitment is made
- Resolving scope disagreements — moving the conversation from "yes/no" to "now/later"
- Solutions scoping: what Method delivers vs. what the client defers
- Any conversation where stakeholders are treating all requirements as equally urgent

## Key Concepts
- **Must Have**: Non-negotiable requirements for the current delivery — without them, the release has no value or cannot function. Must Haves define the minimum viable release. If all Must Haves aren't delivered, the release should not go out
- **Should Have**: Important but not critical — the release has value without them, but they significantly improve it. Should Haves are typically 80% of the value but 20% of the arguments
- **Could Have**: Nice to have — small improvements that can be included if capacity allows, or deferred with minimal impact. Candidates for cut when time pressure mounts
- **Won't Have (this time)**: Explicitly out of scope for this release — not a rejection, but a documented deferral. The "this time" qualifier is important: it signals the item may appear in a future release and prevents stakeholders from feeling shut out
- **The 60% Rule**: A common heuristic: Must Haves should consume no more than 60% of available capacity. This creates a buffer for Should Haves and absorbs estimation variance — if everything is a Must Have, there is no contingency
- **MoSCoW vs. Stack Ranking**: MoSCoW creates tiers, not a ranked list. Multiple items can share the same tier. This is both a strength (tier-based conversations are easier) and a weakness (it doesn't resolve priority within a tier)
- **Dynamic Nature**: MoSCoW categories shift across iterations. A Could Have this sprint may become a Must Have next sprint as dependencies change

## Method Application
Method uses MoSCoW in solutions scoping, requirements analysis, and delivery planning. It provides the vocabulary for scope negotiation — a client who says "everything is critical" can be redirected: "If we ran out of time on day 59, which of these 30 items would you be comfortable shipping without?" That question produces MoSCoW classifications whether stakeholders realize it or not.

## Consulting Insight
🎯 **Consulting Tool — MoSCoW Prioritization**: The most productive use of MoSCoW is not filling out the matrix — it's the conversation that the matrix forces. Ask stakeholders to categorize requirements and then challenge every Must Have: "What happens if this doesn't ship on day one?" Most Must Haves become Should Haves under that question. The residual true Must Haves define the real scope commitment. → `consulting-tools-repository/moscow-prioritization.md`

## Related Entries
- [RICE Scoring](rice-scoring.md) — within a MoSCoW tier, RICE provides quantitative ranking
- [Kano Model](kano-model.md) — Kano classification should inform MoSCoW tier assignment; Basic Needs are Must Haves, Excitement features are often Should or Could Haves
- [Iron Triangle](iron-triangle.md) — MoSCoW operationalizes the scope vertex of the Iron Triangle
- [Dependency Mapping](dependency-mapping.md) — Must Haves with hard dependencies may constrain delivery order regardless of MoSCoW tier
- [Decision Matrix](decision-matrix.md) — structured scoring for prioritization decisions within a MoSCoW tier

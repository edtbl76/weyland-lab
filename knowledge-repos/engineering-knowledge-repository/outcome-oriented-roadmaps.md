---
id: outcome-oriented-roadmaps
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [continuous-discovery, agile-practices, four-key-metrics, estimation-and-planning, shape-up]
complexity: foundational
---

# Outcome-Oriented Roadmaps

## What It Is
A product roadmap organized around business outcomes and customer goals rather than a feature delivery schedule. Traditional roadmaps list features and their dates ("Ship X by Q2, Y by Q3"). Outcome-oriented roadmaps list the problems to solve or results to achieve ("Reduce checkout abandonment by 15% in Q2", "Enable self-service account provisioning in Q3") and treat specific features as hypotheses about how to achieve those outcomes — not as commitments. Popularized by Marty Cagan, Teresa Torres, and the Product-Led approach, outcome-oriented roadmaps are better aligned with modern product development because they acknowledge that the best solution to a problem is often discovered, not planned.

## When to Apply
- Product teams moving from output-focused (feature factories) to outcome-focused development
- When stakeholder roadmaps have become commitment lists that create pressure to deliver features regardless of whether they solve the problem
- Agile and discovery-oriented teams where the specific implementation is expected to evolve
- When aligning engineering, product, and business around what success looks like, not what will be built

## Key Concepts
- **Outputs vs. Outcomes**: An output is a deliverable (a feature, a page, an API). An outcome is a measurable change in behavior or result (reduced churn, faster time-to-value, improved NPS). Output roadmaps commit to outputs; outcome roadmaps commit to outcomes and treat outputs as hypotheses
- **Now / Next / Later Format**: A common outcome roadmap format:
  - *Now*: Active work — specific initiatives underway, with teams assigned and progress visible
  - *Next*: Committed outcomes for the near term (1-2 quarters) — clear goals, but specific solutions may still be open
  - *Later*: Strategic bets and problem areas — described as outcomes, not features. Explicitly vague to preserve flexibility
- **Opportunity Solution Tree**: Teresa Torres' framework for structuring outcome-oriented discovery — one desired outcome at the root, opportunities (problems/needs) in the middle, solutions (features/experiments) at the leaves. The roadmap tracks which opportunities the team is pursuing; specific solutions are hypotheses
- **Metrics as Guardrails**: Every roadmap item has a success metric. "Reduce time to first value for new users" is accompanied by a measure ("users complete first meaningful action within 3 minutes") so the team knows when the outcome is achieved and when to stop
- **Communicating to Stakeholders**: Outcome roadmaps require stakeholder education. Business partners accustomed to feature lists need to understand that specific features are hypotheses, and the team may solve the problem differently than planned. The commitment is to the outcome, not the specific implementation
- **Anti-Patterns**:
  - Renaming features as outcomes ("Improve dashboard" is not an outcome)
  - Committing to outcomes AND specific solutions (defeats the purpose)
  - Treating "Later" as a promise rather than a direction signal

## In Practice
Method product engagements use outcome-oriented roadmaps for client-facing product strategy discussions. The Now/Next/Later format is the default for quarterly roadmap reviews. Success metrics are defined for every Now and Next item before work begins. During construction phases, specific features are treated as hypotheses — if a simpler solution achieves the outcome, the team takes the simpler path rather than delivering the originally planned feature.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Outcome-Oriented Roadmaps**: A feature roadmap is a list of bets about what solutions will achieve outcomes — but it presents bets as certainties. When stakeholders treat roadmap items as commitments, teams build features even when early evidence suggests a different solution would work better. Outcome-oriented roadmaps make the bet explicit: we're committing to the outcome, not the specific solution. The biggest adoption challenge is stakeholder communication — business partners want to know "what will you build?", not "what problem will you solve?". That conversation is worth having early. → `engineering-knowledge-repository/outcome-oriented-roadmaps.md`

## Related Entries
- [Continuous Discovery](continuous-discovery.md) — outcome-oriented roadmaps require ongoing discovery to identify which solutions best achieve committed outcomes
- [Agile Practices](agile-practices.md) — outcome-oriented roadmaps align with agile's adaptability principle; specific solutions emerge through iteration
- [Four Key Metrics](four-key-metrics.md) — DORA metrics can inform engineering-level outcomes on a platform or DevOps roadmap
- [Estimation and Planning](estimation-and-planning.md) — outcome roadmaps reduce the need for precise feature-level estimates; outcomes have targets, not delivery dates
- [Shape Up](shape-up.md) — Shape Up's appetite model aligns with outcome-oriented thinking: fixed time, flexible scope, outcome-focused

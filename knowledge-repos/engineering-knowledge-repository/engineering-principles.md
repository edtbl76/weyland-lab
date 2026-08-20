---
id: engineering-principles
tags: [reference, team-practices]
surfaces-at: [requirements-analysis, application-design]
related: [architecture-decision-records, definition-of-done, developer-experience, four-key-metrics]
complexity: foundational
---

# Engineering Principles

## What It Is
A team's documented, shared set of values and guidelines that guide technical decision-making. Engineering principles are not rules for every situation — they are heuristics that resolve ambiguity consistently when multiple valid approaches exist. Well-crafted principles reflect the team's learned experience: what has worked, what has failed, what trade-offs the team consistently prefers. Without explicit principles, decisions are inconsistent and new team members have no reference for what "good" looks like on this team.

## When to Apply
- At project inception (Iteration 0) — establish principles before the first technical decisions are made
- When a team grows and onboards new members — principles replace tribal knowledge
- When recurring debates about the same trade-offs indicate implicit disagreement about values
- When reviewing ADRs — principles should be cited as the rationale for decisions

## Key Concepts
- **Opinionated, Not Exhaustive**: Good engineering principles don't cover every scenario — they cover recurring decision points where the team has a clear preference
- **Examples Over Abstractions**: "Prefer boring technology over novel technology unless the novel choice solves a specific problem" is better than "Make pragmatic technology choices"
- **Principles vs. Standards**: Principles guide judgment; standards are specific rules (e.g., "use PostgreSQL for relational data" is a standard, not a principle)
- **Living Document**: Principles should be revisited as the team learns — a principle that no longer reflects how the team works should be updated or removed
- **Cited in ADRs**: When writing an ADR, reference the principle(s) that support the decision — creates traceability between values and choices
- **Common Engineering Principles**: "Simple before clever," "Build for observability from day one," "Prefer managed services over self-managed," "Optimize for changeability over optimization," "Explicit over implicit"
- **Onboarding Value**: Engineering principles are one of the first documents a new engineer should read — they explain why the codebase looks the way it does

## In Practice
Method creates an `ENGINEERING_PRINCIPLES.md` file in the repository root during Iteration 0 of client engagements. The document is short (5-10 principles), opinionated, and specific to the engagement context. Principles are reviewed in retrospectives and updated when the team's experience contradicts them. ADRs cite the relevant principle in their decision rationale.

## Engineering Knowledge
💡 **Engineering Knowledge — Engineering Principles**: Write down what your team believes before the first technical debate happens. 5-10 opinionated principles beat 50 vague ones. "Prefer managed services unless cost or feature requirements dictate otherwise" is actionable; "Make pragmatic choices" is not. Store in `ENGINEERING_PRINCIPLES.md` in the repo root. Cite principles in ADRs to connect values to decisions. Revisit in retrospectives — principles that don't reflect current practice should be updated or removed. → `engineering-knowledge-repository/team-practices/engineering-principles.md`

## Related Entries
- [Architecture Decision Records](architecture-decision-records.md) — ADRs cite engineering principles as decision rationale
- [Definition of Done](definition-of-done.md) — DoD operationalizes engineering principles as concrete quality gates
- [Developer Experience](developer-experience.md) — engineering principles set the bar for what good developer experience means on this team
- [Four Key Metrics](../architectural-philosophy/four-key-metrics.md) — DORA metrics are a set of engineering principles made measurable

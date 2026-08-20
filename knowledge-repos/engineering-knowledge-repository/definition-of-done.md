---
id: definition-of-done
tags: [methodology, team-practices]
surfaces-at: [requirements-analysis, user-stories]
related: [architecture-decision-records, technical-debt-management, code-review-practices]
complexity: foundational
---

# Definition of Done (DoD)

## What It Is
A shared, explicit checklist of criteria that a piece of work must meet before the team considers it complete. The Definition of Done prevents ambiguity about what "done" means — without it, "done" means different things to different team members, and work that passes a sprint review may still lack tests, documentation, deployment scripts, or performance validation. The DoD is a quality contract the team makes with itself.

## When to Apply
- All delivery teams — the DoD should be established before the first sprint begins
- When quality issues are being discovered after stories are closed
- When work repeatedly needs remediation after acceptance — the remediation items belong in the DoD
- When new engineers are unclear about what's expected before calling work complete

## When Not to Apply
- Applying the DoD rigidly to exploratory spikes or prototypes — time-boxed investigations may intentionally produce throwaway code

## Key Concepts
- **Team-Owned**: The team writes and maintains the DoD — it reflects the team's quality standards, not an external mandate
- **Living Document**: The DoD evolves as the team learns — add criteria when recurring quality issues emerge, remove criteria that are no longer relevant
- **Example Criteria**: Code reviewed and approved, unit tests written and passing, CI pipeline green, deployed to staging, acceptance criteria verified, no new Sev-1 issues, documentation updated, monitoring/alerting configured
- **Ready vs. Done**: "Definition of Ready" (criteria for picking up a story) is different from "Definition of Done" (criteria for completing one)
- **Velocity Honesty**: A DoD that includes tests, reviews, and deployments produces a lower story velocity than one that doesn't — but it's honest velocity. Teams without a strong DoD overcount velocity and accumulate hidden debt.

## In Practice
The Definition of Done is established in Method engagements during Iteration 0 sprint planning. It's posted visibly in the team's workspace (Jira, Confluence, or the repo README). When a story is demoed in sprint review, the DoD is the checklist — if any item is missing, the story doesn't close. The DoD is reviewed and refined at each retrospective.

## Engineering Knowledge
💡 **Engineering Knowledge — Definition of Done**: "Done" without a shared definition isn't done — it's "done enough for now, will fix later." Write the DoD before the first sprint: code reviewed, tests written, CI green, deployed to staging, monitoring configured. When quality issues keep appearing after acceptance, add them to the DoD. Velocity measured against a strong DoD is honest velocity — a team without a DoD overstates progress and defers debt. → `engineering-knowledge-repository/team-practices/definition-of-done.md`

## Related Entries
- [Code Review Practices](code-review-practices.md) — code review is typically a DoD criterion
- [Technical Debt Management](technical-debt-management.md) — a strong DoD prevents the technical debt that accumulates when "done" is under-defined

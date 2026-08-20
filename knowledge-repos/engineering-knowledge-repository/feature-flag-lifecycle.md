---
id: feature-flag-lifecycle
tags: [methodology, deployment, developer-experience]
surfaces-at: [application-design, functional-design]
related: [feature-flags, progressive-delivery, technical-debt-management, ci-cd, dynamic-configuration-management]
complexity: intermediate
---

# Feature Flag Lifecycle

## What It Is
The practices governing how feature flags are created, used, and retired — ensuring that flags serve their purpose (safe deployment, progressive rollout, A/B testing) without accumulating as permanent code branches that add complexity and maintenance cost. Feature flags are not permanent abstractions; they are temporary mechanisms that should be removed once their purpose is fulfilled. Without lifecycle discipline, a codebase accumulates dozens of dead flags, conditional code paths that can never be removed, and flags that developers are afraid to delete because nobody knows if they're still active. This technical debt is silent, expensive, and occasionally catastrophic (the Knight Capital incident involved dead code activated by an old flag).

## When to Apply
- Any team using feature flags at scale (10+ active flags)
- When the feature flag count has grown faster than flag retirements
- When engineers are uncertain about which flags are safe to delete
- After adopting progressive delivery practices — lifecycle management must accompany flag adoption

## Key Concepts
- **Flag Types and Lifespans**: Different flag types have different expected lifespans:
  - *Release toggles*: Short-lived (days to weeks). Enable progressive rollout of a new feature. Target lifespan: removed within 1-2 sprints of full rollout
  - *Experiment flags*: Medium-lived (weeks to months). Control A/B test variants. Target lifespan: removed after experiment concludes and variant is chosen
  - *Ops/kill switch flags*: Long-lived. Allow operational control (disable a feature under load, enable maintenance mode). May be permanent but should be documented as intentionally permanent
  - *Permission/entitlement flags*: Long-lived. Control access by tier, plan, or user group. Should be managed as product configuration, not in feature flag tools
- **Flag Ownership**: Every flag has a named owner — the team or individual responsible for its retirement. Flag creation should require: flag ID, owner, type, purpose, expected expiry date. This metadata enables automated staleness detection
- **Staleness Detection**: Flags not evaluated in production for N days (typically 30-90 days) are flagged as stale. Stale flags are candidates for removal. LaunchDarkly, Unleash, and Flagsmith provide staleness tracking. Connect stale flag alerts to a cleanup ticket workflow
- **Removal Process**:
  1. Confirm the flag is fully rolled out (100% on) or fully retired (0% off) and has been so for the removal threshold period
  2. Remove flag evaluation code from the application — leave no conditional logic behind
  3. Delete the flag configuration from the flag management system
  4. Verify tests still pass — flag removal should simplify code, not introduce failures
  5. Deploy and confirm no regression
- **Flag Debt Reviews**: Regularly review active flags (monthly or sprint-by-sprint) to identify flags past their expected removal date. Include "flag cleanup" items in sprint backlog alongside feature work
- **Anti-Patterns**:
  - *Permanent release flags*: Release toggles that become permanent because nobody wants to delete them. Every release flag should have a removal ticket created at the time the flag is created
  - *Flag-of-flags*: Nesting flags inside flags for complex conditional logic. If you need flag combinations, you've exceeded the appropriate scope of feature flags
  - *Flags for configuration*: Using release toggle tools for long-lived operational configuration. Operational config belongs in a configuration management system with appropriate controls
- **Knight Capital Warning**: In 2012, Knight Capital lost $440M in 45 minutes because dead code was accidentally activated by an old unused flag. Unretired flags accumulate dead code paths that can be accidentally activated. This is not a hypothetical risk

## In Practice
Method establishes feature flag lifecycle standards at the start of any engagement that uses flags. LaunchDarkly or Unleash is configured with flag type metadata and expected expiry dates. Stale flag alerts are routed to the owning team's Slack channel. Sprint planning includes a standing check for flags past their expected removal date. Release flags are removed within 2 sprints of achieving 100% rollout.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Feature Flag Lifecycle**: Feature flags are not free — each flag is a code branch that someone has to maintain, understand, and eventually remove. The cost of flag cleanup is small; the cost of flag accumulation is large (complexity, dead code, occasional disaster). Enforce lifecycle discipline from the start: every flag has an owner, a type, and an expected expiry date. Automate staleness detection. The hardest flags to delete are the ones nobody's sure about — metadata prevents this from the start. → `engineering-knowledge-repository/feature-flag-lifecycle.md`

## Related Entries
- [Feature Flags](feature-flags.md) — feature flags require lifecycle management to prevent accumulation as technical debt
- [Progressive Delivery](progressive-delivery.md) — progressive delivery uses release toggles that must be retired after rollout completes
- [Technical Debt Management](technical-debt-management.md) — unretired feature flags are a form of technical debt with unique operational risk
- [CI/CD](ci-cd.md) — CI/CD pipelines can enforce flag hygiene by failing builds with flags past their expiry date
- [Dynamic Configuration Management](dynamic-configuration-management.md) — long-lived operational flags belong in dynamic configuration, not feature flag tools

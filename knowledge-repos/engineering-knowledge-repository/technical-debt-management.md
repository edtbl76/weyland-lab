---
id: technical-debt-management
tags: [methodology, team-practices, developer-experience]
surfaces-at: [requirements-analysis, application-design]
related: [architecture-decision-records, yagni-principle, four-key-metrics, evolutionary-architecture]
complexity: intermediate
---

# Technical Debt Management

## What It Is
The intentional practice of identifying, tracking, and systematically repaying technical shortcuts taken in a codebase. Ward Cunningham coined the metaphor: like financial debt, technical debt accumulates interest — the longer it persists, the more it costs to work around it. Technical debt is sometimes intentional (a deliberate shortcut with a plan to revisit) and sometimes inadvertent (discovered later). Effective management distinguishes between types and prioritizes repayment strategically.

## When to Apply
- Any production codebase — all code accumulates debt over time
- Sprint planning — allocate a percentage of capacity to debt reduction alongside feature work
- Before high-stakes milestones (new feature development, scaling) — address debt that would block or destabilize the work ahead
- When delivery velocity is declining despite team capacity remaining constant — debt is the likely cause

## When Not to Apply
- Debt hunting as an excuse to rewrite everything — not all debt warrants repayment
- Treating all code that "could be better" as debt — distinguish debt (shortcuts with real cost) from preference (different style choices)

## Key Concepts
- **Types of Debt**:
  - *Deliberate*: A known shortcut with a plan ("we'll do proper error handling in iteration 2")
  - *Inadvertent*: Discovered later ("we didn't know this pattern would cause problems")
  - *Bit Rot*: Code that was fine when written but has degraded as the system evolved around it
- **Interest**: The ongoing cost of working around the debt — slower development, more bugs, harder onboarding
- **Debt Register**: A tracked backlog of known debt items — ID, description, estimated cost of not fixing, priority
- **Debt Budget**: Allocate 10-20% of sprint capacity to debt reduction — sustainable debt repayment alongside feature delivery
- **Tech Debt vs. Features**: Communicate debt repayment in business terms — "this refactor will reduce the time to add any payment method by 3x"
- **ADRs for Debt**: Architecture Decision Records should document deliberate shortcuts — "we're using this hack because X; we'll address it when Y"

## In Practice
Technical debt management is a standing agenda item in Method engineering engagements. The debt register lives in the issue tracker alongside feature work. Debt is prioritized based on its interest rate — high-traffic code paths with bugs earn more interest than rarely-touched modules. The 10-20% budget rule creates sustainable cadence without derailing feature commitments.

## Engineering Knowledge
💡 **Engineering Knowledge — Technical Debt Management**: All codebases accumulate debt. The question is whether you manage it intentionally or let it compound until it brings delivery to a halt. Keep a debt register, allocate 15% of sprint capacity to repayment, and communicate in business terms — "this refactor will cut feature delivery time by 30%." Document deliberate shortcuts in ADRs so they're discoverable. Debt you don't track is debt that grows unnoticed. → `engineering-knowledge-repository/team-practices/technical-debt-management.md`

## Related Entries
- [Architecture Decision Records](architecture-decision-records.md) — ADRs document deliberate technical shortcuts and their planned remediation
- [YAGNI Principle](../architectural-philosophy/yagni-principle.md) — YAGNI prevents speculative complexity; debt management addresses unavoidable accumulated complexity
- [Evolutionary Architecture](../architectural-philosophy/evolutionary-architecture.md) — evolutionary architecture principles minimize debt by designing for changeability

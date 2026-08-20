---
id: architecture-decision-records
tags: [methodology, team-practices]
surfaces-at: [application-design, requirements-analysis]
related: [engineering-principles, technical-debt-management, evolutionary-architecture]
complexity: foundational
---

# Architecture Decision Records (ADRs)

## What It Is
Lightweight documents that capture an architectural decision, the context that drove it, the options considered, and the rationale for the choice. Coined by Michael Nygard. An ADR answers: "Why is this built this way?" — a question that otherwise disappears from institutional memory the moment the engineer who made the decision leaves the team.

## When to Apply
- Any significant architectural decision — technology choices, structural patterns, security approaches, data model choices
- When a decision will be difficult or expensive to reverse
- When multiple options were viable and future engineers need to understand why this one was chosen
- When onboarding new engineers — the ADR history explains the system's shape

## When Not to Apply
- Routine implementation decisions with no architectural impact
- Temporary decisions that will clearly be revisited soon
- Decisions already fully captured in official design documents or RFCs

## Key Concepts
- **Status**: The ADR's lifecycle state — Proposed, Accepted, Superseded, Deprecated
- **Context**: The forces and constraints that made this decision necessary — business context, technical constraints, team knowledge
- **Decision**: What was decided — specific and unambiguous
- **Consequences**: What the decision implies — tradeoffs accepted, future constraints, what becomes easier or harder
- **Superseded By**: When an ADR is revisited, the new ADR references the old one — preserving the reasoning history
- **Format**: ADRs are short — typically one page. The value is captured context, not exhaustive documentation.
- **Storage**: ADRs live in the repository alongside code — `docs/decisions/` or `/adr/`. Source-controlled, version-tracked, always up-to-date with the codebase.

## In Practice
ADRs are standard in Method engagements for any significant architectural choice. The template (Context/Decision/Consequences) keeps them short and scannable. The discipline is writing them at decision time, not retrospectively. New engineers on a project should read the ADR history before touching the architecture — it's the fastest way to understand why the system is shaped the way it is.

## Engineering Knowledge
💡 **Engineering Knowledge — Architecture Decision Records**: Write a one-page document every time you make a significant architectural choice: what was decided, why, what options were rejected, and what tradeoffs were accepted. Store ADRs in the repo — they're part of the codebase. Six months from now, when someone asks "why did we use Kafka instead of SQS?", the ADR answers it without requiring the original engineer. Short and timely beats long and retroactive every time. → `engineering-knowledge-repository/team-practices/architecture-decision-records.md`

## Related Entries
- [Evolutionary Architecture](../architectural-philosophy/evolutionary-architecture.md) — ADRs track the decision points in an architecture's evolution
- [Technical Debt Management](technical-debt-management.md) — ADRs for accepted technical shortcuts document the debt for future remediation

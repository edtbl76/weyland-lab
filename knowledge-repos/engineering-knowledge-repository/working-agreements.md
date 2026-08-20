---
id: working-agreements
tags: [methodology, developer-experience, team-practices]
surfaces-at: [application-design]
related: [code-review-practices, developer-onboarding, pair-programming, mob-programming, inner-source]
complexity: foundational
---

# Working Agreements

## What It Is
Explicit, team-authored norms about how a team works together — how decisions are made, how code is reviewed, when meetings happen, what "done" means, and how conflict is resolved. Working agreements make implicit expectations explicit and shared, reducing friction from misaligned assumptions. They are especially important for new teams, distributed teams, and consulting engagements where engineers come from different backgrounds and may have very different expectations about how software teams operate.

## When to Apply
- When forming a new team (define agreements before conflicts arise)
- When a consulting engagement kicks off (client and consulting engineers need shared norms)
- When a team is experiencing recurring friction around process (missing reviews, unclear ownership, meeting fatigue)
- At the start of each major iteration or quarter as a reflection and refinement moment

## Key Concepts
- **What to Cover**:
  - *Communication*: Primary channel (Slack, Teams), expected response time, when to escalate from async to sync
  - *Code Review*: PR size expectations, reviewer turnaround time (e.g., 24-hour SLA), what "approved" means (rubber stamp vs. genuine review), how to handle disagreements
  - *Meetings*: Which meetings are mandatory, async-first vs. sync-first culture, no-meeting blocks, meeting preparation expectations
  - *Working Hours*: Core hours for overlap (especially for distributed teams), flexibility outside core hours, on-call expectations
  - *Definition of Done*: What must be true before a story is considered complete — tests written, documentation updated, reviewed, deployed to staging
  - *Decision Making*: Who has final say on technical decisions, how to escalate disagreements, when to use RFCs or ADRs
  - *Availability and Focus Time*: Expectations around deep work blocks, notification settings, calendar transparency
- **Format**: Short, numbered list of agreements that fit on one page. Lengthy process documents are not working agreements — they're policy. Working agreements are conversational norms, not rules
- **Co-Created**: Working agreements should be created together by the team, not handed down by a manager or lead. Teams own agreements they helped write. A facilitator (Scrum Master, PM, lead) runs the creation session
- **Living Document**: Review and update working agreements at retrospectives. Agreements that no longer reflect how the team works are misleading — update or remove them
- **Explicit vs. Assumed**: The value of working agreements is making implicit assumptions explicit. "We do code reviews" is not an agreement. "PRs get a first review within 24 hours; we use the GitHub comment threads for discussion; approval means the reviewer is confident the change is correct" is an agreement
- **Definition of Ready (DoR)**: Stories are "ready" to be worked when acceptance criteria are defined, dependencies are identified, and the team understands what done looks like. Teams that start stories without this clarity waste development time on ambiguity
- **Definition of Done (DoD)**: Stories are "done" when code is written, reviewed, tests pass, documentation is updated (if applicable), and the change is deployed to staging. "Done" does not mean "merged to main" — it means shippable

## In Practice
Method kicks off each client engagement with a working agreements session in the first week. A standard template covers code review SLAs, communication channels, meeting norms, definition of done, and decision-making authority. Agreements are documented in the team wiki and reviewed at each sprint retrospective. Agreements that are consistently violated are either enforced through automation (CI gates, PR templates) or removed as aspirational rather than actual norms.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Working Agreements**: The best time to define working agreements is before a team has its first conflict about process — not after. Code review turnaround time, PR size, and definition of done are the three agreements that have the highest impact on team velocity and should always be made explicit. On consulting engagements, misaligned expectations between client and consulting engineers about how decisions are made is a common source of tension — working agreements surface and resolve this early. A working agreement that exists only in a document is not a working agreement — review it at every retrospective. → `engineering-knowledge-repository/working-agreements.md`

## Related Entries
- [Code Review Practices](code-review-practices.md) — code review norms are one of the most impactful working agreements a team can define
- [Developer Onboarding](developer-onboarding.md) — working agreements are part of the team handbook that new engineers receive on day 1
- [Pair Programming](pair-programming.md) — when and how to pair is a common working agreement topic
- [Mob Programming](mob-programming.md) — ensemble working norms benefit from explicit agreements about roles and facilitation
- [Inner Source](inner-source.md) — inner source contribution guidelines are a form of working agreements for cross-team contributions

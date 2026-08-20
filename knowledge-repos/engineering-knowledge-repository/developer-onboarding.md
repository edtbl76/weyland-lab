---
id: developer-onboarding
tags: [methodology, developer-experience, team-practices]
surfaces-at: [application-design]
related: [local-development-environment, documentation-as-code, working-agreements, inner-source]
complexity: foundational
---

# Developer Onboarding

## What It Is
The structured process of getting a new engineer from "just joined the team" to "independently productive" as quickly as possible. Good onboarding means a new developer can set up their local environment, understand the architecture, make a meaningful first contribution, and know how the team works — all within their first week. Poor onboarding means days of confusion, tribal knowledge dependencies, and a new engineer feeling unsupported. For consulting firms, fast onboarding is a competitive advantage: engineers must contribute quickly across multiple engagements.

## When to Apply
- Every time a new engineer joins the team (plan once, apply repeatedly)
- When a team has grown to where institutional knowledge is no longer informal
- When onboarding feedback reveals consistent friction points
- When a consulting engagement starts and client engineers need to contribute quickly

## Key Concepts
- **Onboarding Documentation**:
  - README: Project overview, architecture summary, how to run locally, how to run tests, how to deploy
  - Architecture Decision Records (ADRs): Why key decisions were made — new engineers shouldn't reverse-engineer historical decisions
  - Runbook: Common operational tasks (how to run a migration, how to add a feature flag, how to debug a production issue)
  - Team handbook: How the team works — standups, planning, code review norms, on-call expectations
- **Day-1 Goal**: New engineer has local environment running, has made a trivial commit (fix a typo, add a test), and has a PR reviewed and merged. Completing a real (even small) contribution on day 1 establishes momentum and validates the development workflow
- **Buddy System**: Assign a dedicated onboarding buddy — a senior engineer who answers questions, pairs on the first few tasks, and checks in daily for the first week. Onboarding without a buddy forces new engineers to interrupt random team members or stay stuck
- **Starter Tasks**: Curate a backlog of genuinely small, well-scoped "good first issues" — low-risk changes with clear acceptance criteria that help the new engineer navigate the codebase. Avoid assigning tasks that require knowing the entire system
- **Architecture Overview Session**: A 1-hour walkthrough of the system architecture by a senior engineer. Covers the main components, data flows, key design decisions, and what's being actively worked on. More efficient than reading documentation alone
- **Access and Credentials Setup Checklist**: New engineers spend significant time requesting access. A documented checklist covering GitHub, AWS, data stores, internal tools, and communication channels — ideally automated via IDP tooling — eliminates this friction
- **30/60/90-Day Plan**: Define what success looks like at 30, 60, and 90 days. By 30 days: shipping features with guidance. By 60 days: independently handling a feature end-to-end. By 90 days: contributing to architectural discussions and mentoring others
- **Onboarding Feedback Loop**: Ask new engineers at the end of week 1 and month 1 what was unclear, broken, or missing. Update the documentation immediately. Onboarding docs that aren't maintained become misleading

## In Practice
Method maintains a team handbook for each engagement with architecture overview, local setup instructions, team norms, and a first-week checklist. New engineers are assigned a buddy and a set of labeled first issues. Day-1 goal is always a merged PR. Access provisioning is handled through a pre-configured Terraform workspace and documented checklist. Onboarding feedback is collected at 2 weeks and used to update docs immediately.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Developer Onboarding**: Measure onboarding quality by time-to-first-PR: if it takes more than a day, there's a friction problem to fix. Onboarding docs that live only in someone's head are a single point of failure — every time you answer the same question twice, write the answer down. Assign a buddy, not a document: human guidance during the first week reduces the time new engineers spend stuck. For consulting teams, fast onboarding is a business requirement — client engagements don't have time for 2-week ramp-ups. → `engineering-knowledge-repository/developer-onboarding.md`

## Related Entries
- [Local Development Environment](local-development-environment.md) — a reproducible local setup is the foundation of day-1 productivity
- [Documentation as Code](documentation-as-code.md) — architecture docs, ADRs, and runbooks are the primary onboarding reading material
- [Working Agreements](working-agreements.md) — team norms and processes are documented as part of onboarding
- [Inner Source](inner-source.md) — inner source practices (CONTRIBUTING.md, contribution guidelines) reduce onboarding friction for cross-team contributors

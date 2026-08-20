---
id: rfcs-and-design-docs
tags: [methodology, team-practices, developer-experience]
surfaces-at: [application-design]
related: [architecture-decision-records, documentation-as-code, working-agreements, engineering-principles, code-review-practices]
complexity: foundational
---

# RFCs and Design Docs

## What It Is
Written proposals that describe the motivation, design, and tradeoffs for a significant technical change before implementation begins. RFCs (Requests for Comments) and design docs create a structured forum for asynchronous technical discussion, surface concerns early, and produce a durable record of why decisions were made. For impactful or irreversible decisions — new services, database schema changes, API contracts, major refactors — writing a design doc first is consistently faster than discovering fundamental problems mid-implementation. The goal is not bureaucracy; it is alignment before commitment.

## When to Apply
- New services, APIs, or significant architectural changes
- Technical decisions with tradeoffs where multiple reasonable options exist
- Changes that will affect multiple teams or services
- Any decision that will be hard to reverse once implemented
- When team alignment is uncertain and early discussion would reduce rework

## Key Concepts
- **RFC vs. ADR**: These are complementary, not alternative:
  - *RFC / Design Doc*: Written before or during design. The proposal is under discussion. Goal: gather feedback, surface concerns, reach alignment
  - *ADR (Architecture Decision Record)*: Written after a decision is made. Records the context, decision, and consequences. Goal: document why we decided what we did for future reference
  - Workflow: RFC → discussion → decision → ADR records the outcome
- **Design Doc Structure** (Google's standard):
  - *Context*: What problem are we solving? Why now?
  - *Goals and Non-Goals*: What will this achieve? What is explicitly out of scope?
  - *Design*: The proposed solution. Diagrams, API shapes, data model changes, system interactions
  - *Alternatives Considered*: What other approaches did we evaluate? Why did we reject them?
  - *Open Questions*: Unresolved concerns that need input or decisions
  - *Implementation Plan*: How will this be built? In what phases?
- **Lightweight vs. Heavyweight**: Match depth to stakes:
  - *1-2 pager*: Small changes, one team impact, low risk. Context + proposal + key tradeoffs
  - *Full design doc*: Cross-team impact, high risk, significant complexity. Full structure above
  - Don't require a 10-page design doc for every PR — reserve the ceremony for decisions that warrant it
- **Review Process**:
  - Share the doc with relevant stakeholders and request feedback by a specific date
  - Use async comments (Google Docs, Notion, GitHub PR on a markdown file) for feedback
  - Schedule a synchronous discussion only if async review doesn't resolve key disagreements
  - Set a clear decision deadline — RFCs that stay "open" indefinitely are not RFCs, they are deferred decisions
- **Template and Tooling**: Store design docs in a central, searchable location (Confluence, Notion, GitHub repo). Use a consistent template — reviewers know where to look for context, alternatives, and open questions. Link design docs from the implementation PR and from the resulting ADR
- **Author Responsibilities**: The RFC author is not obligated to implement every suggestion, but must engage with all feedback. Acknowledge concerns; either adopt the suggestion, explain why you won't, or add to open questions. Ghosting feedback kills the process
- **Common Failure Modes**:
  - Writing the doc after the implementation decision is already made (performative)
  - RFCs that never reach a decision (analysis paralysis)
  - Requiring design docs for everything (overhead kills velocity)
  - Not linking the RFC to the implementation — loses the context trail

## In Practice
Method requires a design doc for any change that crosses service boundaries, introduces a new external dependency, or changes a public API contract. A 1-pager is sufficient for contained changes; full design docs for cross-team impact. Design docs live in Confluence, linked from Jira epics and implementation PRs. Review window is 3-5 business days; the author calls the decision and records it in an ADR. Design docs are searchable — new engineers read them to understand historical technical decisions.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — RFCs and Design Docs**: A design doc written in 2 hours that catches a fundamental flaw saves 2 weeks of implementation. The "alternatives considered" section is the most important part — it shows you've thought about the problem rather than jumping to a solution, and it answers the most common review question ("why not X?"). The process only works if there is a clear decision deadline and a clear decision maker. Keep the template lightweight enough that engineers write docs for real; overly formal processes get bypassed. Link every design doc to the implementation PR and to the resulting ADR — the three together tell the complete story. → `engineering-knowledge-repository/rfcs-and-design-docs.md`

## Related Entries
- [Architecture Decision Records](architecture-decision-records.md) — ADRs record the outcome of decisions initiated in RFCs; complementary artifacts
- [Documentation as Code](documentation-as-code.md) — design docs stored as markdown in Git benefit from version control and PR-based review
- [Working Agreements](working-agreements.md) — when to write an RFC is a working agreement that teams must define explicitly
- [Engineering Principles](engineering-principles.md) — design docs make engineering principles explicit in concrete decisions
- [Code Review Practices](code-review-practices.md) — code review is more effective when reviewers have read the design doc for the change they are reviewing

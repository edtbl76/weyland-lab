---
id: agile-practices
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [shape-up, lean-software-development, continuous-discovery, working-agreements, four-key-metrics]
complexity: foundational
---

# Agile Practices

## What It Is
A family of iterative, collaborative software development methodologies that prioritize delivering working software in short cycles, responding to change over following a plan, and close collaboration between engineers, product managers, and stakeholders. Agile is the dominant delivery framework for software teams. The most common implementations are Scrum (sprint-based, with defined ceremonies) and Kanban (flow-based, continuous delivery). For consulting engagements, agile practices provide the delivery structure that balances client visibility and control with engineering effectiveness.

## When to Apply
- Every software delivery engagement (the question is which agile practices to use, not whether to use them)
- When establishing delivery cadence at the start of a new engagement
- When a team is experiencing coordination problems, unclear priorities, or low delivery predictability

## Key Concepts
- **Scrum**: A sprint-based framework with fixed-length iterations (1-2 weeks common). Core ceremonies:
  - *Sprint Planning*: Select items from the backlog for the sprint; commit to a sprint goal
  - *Daily Standup*: Brief daily sync (15 min); what did I do yesterday? what will I do today? any blockers?
  - *Sprint Review (Demo)*: Demonstrate completed work to stakeholders; gather feedback
  - *Retrospective*: What went well? What could improve? Specific action items for next sprint
  - Roles: Product Owner (defines what), Scrum Master (facilitates process), Dev Team (defines how)
- **Kanban**: Flow-based; work items move through defined stages (Backlog → In Progress → Review → Done). No fixed iterations. Metrics: cycle time (how long items take), WIP (work in progress) limits (prevent overloading the team). Better for: operational work, support teams, teams with unpredictable work arrival
- **Scrumban**: Hybrid — sprint planning cadence with Kanban flow and WIP limits. Common for teams transitioning or with mixed project/support work
- **Backlog Management**:
  - Product backlog: Ordered list of all work. Priority is explicit — item 1 is more important than item 2
  - Backlog grooming/refinement: Regular sessions where the team reviews upcoming work, clarifies requirements, and estimates before sprint planning
  - Items should have acceptance criteria before entering a sprint
- **Definition of Ready**: Work is ready to be picked up when: acceptance criteria defined, dependencies identified, team understands scope. Starting work without this clarity wastes sprint capacity
- **Definition of Done**: Work is done when: code written and reviewed, tests pass, documentation updated (if applicable), deployed to staging. "Done" means shippable, not just merged. See [Definition of Done](definition-of-done.md)
- **Velocity**: The amount of work a team completes per sprint (measured in story points or items). Tracks capacity over time; used for sprint planning (don't commit more than average velocity). Not a performance metric — don't compare velocity between teams
- **Sprint Goal**: A single sentence describing what the sprint should achieve. Provides focus and enables trade-offs: if a lower-priority item can be dropped to protect the sprint goal, it should be. Teams without a sprint goal complete a list of tasks; teams with a sprint goal deliver an outcome
- **Agile at Consulting Firms**: Client visibility and control matter more in consulting than in product companies. Weekly client check-ins or sprint reviews keep clients informed and enable course correction. Clear definition of roles (who is the Product Owner?) prevents unclear ownership

## In Practice
Method uses 2-week sprints on client engagements. Sprint planning includes the client Product Owner. Sprint reviews include a demo to the client and a retrospective with the delivery team. Standups are async on distributed teams (written updates in Slack), synchronous for co-located teams. Backlog is maintained in Jira; items require acceptance criteria before sprint planning. Velocity is tracked per engagement; sprint goals are set in every planning session.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Agile Practices**: The mechanics of Scrum (sprints, ceremonies) are less important than the principles behind them: short feedback loops, visible work, regular reflection, and working software over documentation. Sprint retrospectives are the highest-leverage ceremony — a team that consistently runs effective retrospectives and acts on their findings will outperform one that goes through the motions. On consulting engagements, sprint reviews with clients are the primary mechanism for building trust and catching misalignment early. Kanban is often better than Scrum for teams with highly variable, unpredictable work (support, infrastructure, on-call-heavy teams). → `engineering-knowledge-repository/agile-practices.md`

## Related Entries
- [Shape Up](shape-up.md) — Shape Up is an alternative to Scrum for product work, emphasizing 6-week cycles and appetite over estimates
- [Lean Software Development](lean-software-development.md) — Lean principles underpin agile; value stream mapping, waste elimination, WIP limits
- [Continuous Discovery](continuous-discovery.md) — continuous discovery integrates user research into agile delivery cadences
- [Working Agreements](working-agreements.md) — agile team norms (standups, code review SLAs, definition of done) are formalized as working agreements
- [Four Key Metrics](four-key-metrics.md) — DORA metrics measure agile delivery effectiveness: deployment frequency, lead time, change failure rate, MTTR

---
id: user-stories
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [agile-practices, behavior-driven-development, definition-of-done, job-stories, estimation-and-planning, continuous-discovery]
complexity: foundational
---

# User Stories

## What It Is
A lightweight format for capturing a unit of user-facing functionality from the perspective of the person who will use it: "As a [role], I want to [capability] so that [benefit]". User stories originated in Extreme Programming (XP) and became the standard unit of work in Scrum. They are intentionally brief — a placeholder for a conversation between product and engineering, not a detailed specification. The value is in the discussion that happens when the team refines a story, not in the written card itself. Acceptance criteria make stories testable and define what "done" means for that story.

## When to Apply
- Sprint planning — stories are the primary unit of work in Scrum
- Backlog refinement — stories are sized, split, and clarified before sprint commitment
- Any time a functional requirement needs to be expressed in terms of user value
- When a team needs a shared language between engineering, product, and design for what is being built

## Key Concepts
- **Format**: `As a [role/persona], I want to [action/capability], so that [benefit/outcome]`
  - Role: who benefits? Be specific — "admin user" is more actionable than "user"
  - Action: what do they want to do? One verb, one object
  - Benefit: why? What value does this create? Without the "so that", stories lose their purpose anchor
- **Acceptance Criteria**: Testable conditions that define when the story is done. Written in Given/When/Then (Gherkin) or as a checklist. Acceptance criteria are the contract between product (what they asked for) and engineering (what they built)
- **INVEST Criteria**: Good user stories are:
  - *Independent*: can be implemented in any order
  - *Negotiable*: the specific solution is not fixed
  - *Valuable*: delivers value to the user or business
  - *Estimable*: the team can size it
  - *Small*: fits in a sprint
  - *Testable*: acceptance criteria are clear
- **Story Splitting**: Large stories (epics) must be split into smaller stories before sprint planning. Common split patterns: by user workflow step, by data variation, by happy path vs. edge cases, by user type. Stories > 1 sprint are hiding complexity
- **Epics**: A collection of related stories that together deliver a larger capability ("User Authentication" → stories for login, registration, password reset, MFA). Epics are roadmap-level; stories are sprint-level
- **Story Points**: Stories are sized in relative units (story points) during refinement. The team uses velocity (average points per sprint) to plan how many stories fit in the next sprint. Sizing is an estimate, not a commitment
- **Limitations**: User stories are not a substitute for design docs, API contracts, or detailed specifications for complex technical work. Use stories for user-facing work; use RFCs or design docs for architecture decisions. Stories describe what, not how — technical implementation details belong in task breakdowns or design docs

## In Practice
Method product engagements use user stories as the primary unit of sprint work for user-facing features. Stories are written by product managers, refined with engineering and design in weekly backlog refinement sessions. Acceptance criteria are written in Given/When/Then format. Stories > 5 story points are split before sprint commitment. Epics group related stories on the roadmap. Job stories are used during discovery to inform the "so that" benefit clause.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — User Stories**: The format is not the point — the conversation is. A user story is a reminder to have a discussion, not a specification to implement from. Stories without acceptance criteria are requirements without a definition of done: the team will build something, but nobody will know if it's correct. Write acceptance criteria before the sprint starts, not after development begins. Split stories aggressively — a story that takes more than a week is a planning risk, not a delivery unit. → `engineering-knowledge-repository/user-stories.md`

## Related Entries
- [Agile Practices](agile-practices.md) — user stories are the primary unit of work in Scrum; refined and committed in sprint planning
- [Behavior-Driven Development](behavior-driven-development.md) — BDD acceptance criteria (Given/When/Then) are the testing specification derived from user story acceptance criteria
- [Definition of Done](definition-of-done.md) — definition of done applies to every user story; acceptance criteria is story-level done
- [Job Stories](job-stories.md) — job stories complement user stories by capturing discovery-phase user motivation behind the "so that" benefit
- [Estimation and Planning](estimation-and-planning.md) — story points estimate user stories; velocity tracks sprint delivery
- [Continuous Discovery](continuous-discovery.md) — continuous discovery generates the user insights that inform well-written user stories

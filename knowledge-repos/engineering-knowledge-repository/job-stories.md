---
id: job-stories
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [user-stories, continuous-discovery, outcome-oriented-roadmaps, behavior-driven-development]
complexity: foundational
---

# Job Stories

## What It Is
A requirements format rooted in the Jobs to Be Done (JTBD) theory that captures why a user takes an action rather than what role they play. Where user stories use the format "As a [persona], I want to [action] so that [benefit]", job stories use "When [situation], I want to [motivation], so I can [expected outcome]". The shift from persona to situation is deliberate — it focuses on the context and causality of behavior, not on assumed user demographics. Developed by Alan Klement, job stories are particularly valuable when user personas are too broad to be meaningful, when the focus is on workflow friction points, or when motivations need to be explored before solutions are defined.

## When to Apply
- When user personas feel artificial or when the same persona has very different motivations in different situations
- Discovery and research phases where understanding user motivation precedes solution design
- When the team is solving for workflow friction rather than building net-new capabilities
- Complementary to user stories: use job stories for discovery, user stories for scrum backlog
- When acceptance criteria need to be grounded in real user motivation rather than assumed behavior

## Key Concepts
- **Format**: `When [situation], I want to [motivation / what I'm trying to do], so I can [expected outcome / benefit]`
  - *Situation*: The specific context that triggers the need — "When I'm reviewing a supplier invoice for approval and the total doesn't match my records"
  - *Motivation*: What the person is trying to accomplish — "I want to quickly see the line items behind the total without leaving the approval screen"
  - *Expected outcome*: The result the person hopes to achieve — "so I can resolve discrepancies without interrupting my approval workflow"
- **Why "When" Instead of "As a"**: Personas describe demographics; situations describe behavior triggers. "As a finance manager" tells you little about what the person is trying to do. "When I'm under deadline to close the books" tells you exactly what context shapes their needs and tolerance for friction
- **Jobs to Be Done Theory**: The underlying theory (Clayton Christensen, Bob Moesta) holds that people "hire" products and features to get jobs done. A job is a goal the person has in a specific situation. JTBD research uncovers jobs through causal interview techniques ("walk me through the last time you...") that reveal switching moments, anxieties, and motivations
- **Job Stories vs. User Stories**: They serve different purposes and can coexist:
  - User stories: backlog items for sprint planning — specific, estimable, testable
  - Job stories: discovery artifacts that capture the "why" behind a set of user stories
  - A single job story may spawn multiple user stories for implementation
- **Forces Analysis**: JTBD distinguishes four forces that drive and resist a behavior change: *Push* (current situation friction), *Pull* (new solution attraction), *Anxiety* (fear of the new), *Habit* (inertia). Understanding these forces produces better product design than feature lists
- **Acceptance Criteria from Job Stories**: Job stories generate situation-grounded acceptance criteria: "Given that I am reviewing an invoice with a discrepancy, when I click the total amount, then the line items expand inline without navigating away from the approval screen"

## In Practice
Method uses job stories during discovery workshops and user research analysis. They are written alongside user research outputs (interview summaries, journey maps) to capture the motivations behind observed behaviors. Product managers use job stories to brief the design team on context before wireframing begins. Job stories are referenced in user story acceptance criteria to preserve the "why" through implementation.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Job Stories**: Job stories are most valuable when you suspect you're solving the wrong problem — when the product backlog is full of features but you're not sure they address real user motivation. The "When [situation]" format forces you to name the context that triggers the need, which frequently reveals that different situations require different solutions (not one solution for all users). Use job stories for discovery, user stories for delivery — they answer different questions. → `engineering-knowledge-repository/job-stories.md`

## Related Entries
- [User Stories](user-stories.md) — job stories complement user stories; job stories capture discovery insights, user stories structure delivery
- [Continuous Discovery](continuous-discovery.md) — job stories are artifacts of discovery research; they capture motivations surfaced in user interviews
- [Outcome-Oriented Roadmaps](outcome-oriented-roadmaps.md) — JTBD theory and job stories align with outcome-oriented product thinking
- [Behavior-Driven Development](behavior-driven-development.md) — job story situations translate naturally into BDD scenario context (Given/When/Then)

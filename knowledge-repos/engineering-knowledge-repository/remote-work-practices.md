---
id: remote-work-practices
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [working-agreements, developer-onboarding, async-programming-patterns, documentation-as-code]
complexity: foundational
---

# Remote Work Practices

## What It Is
The conventions and practices that enable distributed and hybrid engineering teams to collaborate effectively across time zones, locations, and communication channels. Remote work changes the default mode of communication from synchronous (in-person) to asynchronous (written), which requires intentional practices to preserve the benefits — faster decision-making, serendipitous collaboration — while compensating for what is lost. For consulting firms with geographically distributed teams and client co-location requirements, remote work practices are essential operational infrastructure.

## When to Apply
- Any team with members in different cities, countries, or time zones
- Hybrid teams where some members are remote and some are in-office
- Consulting engagements with distributed teams or client/consultant timezone differences
- Any team where meeting culture is causing calendar overload or productivity loss

## Key Concepts
- **Async-First Communication**: Default to written, asynchronous communication rather than synchronous meetings. Write decisions, context, and status updates where they can be read at any time. This does not mean no meetings — it means meetings are reserved for discussions that genuinely need real-time interaction
  - Post decisions and context in Slack channels with enough context for someone reading 8 hours later
  - Write meeting agendas in advance; post summaries and decisions after
  - Avoid "can we jump on a call?" as the default response to any non-trivial question
- **Written Culture**: Distributed teams with strong written cultures are more effective than those relying on verbal communication that doesn't persist. Invest in writing quality: clear, complete Slack messages, thorough PR descriptions, decisions documented in Confluence/Notion
- **Time Zone Management**:
  - Define core overlap hours — the window when all team members are expected to be available for synchronous collaboration. Typically 3-4 hours per day
  - Schedule recurring meetings within core hours; don't schedule a weekly standup that requires someone to join at 7am or 10pm
  - For teams spanning > 6 hours of time zone difference, consider asynchronous standups (written daily updates in Slack)
  - Use time zone-aware scheduling tools (World Time Buddy, Google Calendar with time zone display)
- **Documentation as a First-Class Communication Channel**: Remote teams produce documentation not as an afterthought but as the primary medium for decision-making, onboarding, and shared context. Runbooks, ADRs, design docs, and team wikis are how distributed teams scale institutional knowledge. See [Documentation as Code](documentation-as-code.md)
- **Meeting Hygiene**:
  - Every meeting needs an agenda published in advance — attendees who don't need the meeting shouldn't attend
  - Start meetings on time; respect calendar blocked time
  - Record decisions explicitly and post them in the team channel after the meeting
  - Limit meeting duration to 30 minutes for focused sync; 60 minutes for structured design discussions
  - Weekly "no-meeting days" protect deep work time
- **Remote Collaboration Tools**:
  - *Synchronous*: Zoom, Google Meet, Teams for video calls; Tuple or Pop for pair programming
  - *Async communication*: Slack, Teams with organized channels (not DMs for team-relevant conversations)
  - *Documentation*: Confluence, Notion, GitHub wiki for persistent written knowledge
  - *Whiteboarding*: Miro, FigJam for visual collaboration
- **Visibility of Work**: In co-located offices, work-in-progress is visible organically. Remote teams require intentional visibility: update Jira tickets, post daily updates, share draft PRs early. "Working out loud" reduces the perception of teammates disappearing into a black box
- **Relationship Building**: Distributed teams need deliberate investment in relationship building — casual connection that happens naturally in-office must be engineered. Virtual coffee chats, optional social time, team off-sites (periodic in-person gatherings), and non-work Slack channels contribute to team cohesion and psychological safety

## In Practice
Method operates async-first on distributed engagements. Core overlap hours are defined at engagement kickoff and documented in working agreements. Standups are Slack-based for teams with > 3 hours timezone spread. Design docs and decisions are written in Confluence within 24 hours of completion. Weekly client status updates are written async. Quarterly in-person gatherings for distributed teams maintain relationships. Pair programming uses Tuple; whiteboarding uses Miro.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Remote Work Practices**: The biggest distributed team failure mode is attempting to replicate in-office synchronous communication patterns through video calls. Async-first requires discipline: write more, call less. For consulting, client trust in distributed teams is built through written status, transparent work visibility, and consistent delivery — not by pretending to be co-located via video calls. Protect overlap hours strictly — don't schedule recurring meetings outside them. Written decisions in a searchable location are more valuable than a 30-minute meeting whose outcomes are lost in someone's notes. → `engineering-knowledge-repository/remote-work-practices.md`

## Related Entries
- [Working Agreements](working-agreements.md) — remote team norms (core hours, async standups, response time expectations) are formalized as working agreements
- [Developer Onboarding](developer-onboarding.md) — remote onboarding requires more explicit documentation and buddy support than in-person onboarding
- [Documentation as Code](documentation-as-code.md) — written documentation is the primary communication channel for distributed teams

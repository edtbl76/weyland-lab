---
id: mob-programming
tags: [methodology, team-practices, developer-experience]
surfaces-at: [code-generation]
related: [pair-programming, test-driven-development, trunk-based-development]
complexity: foundational
---

# Mob Programming

## What It Is
A practice where the entire team works together on the same thing, at the same time, on one computer. One person (the Driver) types; everyone else (the Navigators) discusses, directs, and reviews in real time. The driver rotates every few minutes. Also called Ensemble Programming. Coined by Woody Zuill. The extension of pair programming from two people to the whole team.

## When to Apply
- Tackling the most complex, highest-risk feature the team is working on
- Onboarding new team members — mobbing transfers knowledge faster than any other technique
- Resolving architectural decisions where the whole team needs shared understanding
- When a problem has stalled a developer and fresh eyes from the full team are needed
- Kickstarting a new codebase or establishing coding patterns that the whole team will follow

## When Not to Apply
- Routine, well-understood tasks where individual focus is more efficient
- Teams larger than 5-6 people — larger groups become difficult to manage and individual engagement drops
- When team members are in significantly different time zones (though async mob sessions are possible)
- All day, every day — most teams mob selectively, not as their constant mode of work

## Key Concepts
- **Driver**: The person at the keyboard — implements what the navigators direct. The driver only types what the navigators say.
- **Navigator**: The rest of the team — directs the driver, discusses approaches, reviews in real time
- **Rotation Timer**: Roles rotate on a short timer (5-15 minutes) — keeps everyone engaged and prevents one person dominating
- **Strong-Style Pairing**: A facilitation rule for mobs — ideas must flow from Navigator's brain to Driver's hands via voice, not keyboard. Keeps the driver from going solo.
- **Whole Team Ownership**: Code written in a mob session is owned by the whole team — no single author, no knowledge silos

## In Practice
Mob programming is Method's recommendation for the highest-complexity work in an engagement sprint. A two-hour mob session on a critical architectural problem is often more valuable than individual work spread over two days. The rotation mechanism keeps engagement high and prevents tunnel vision. Remote mobbing tools (VS Code Live Share, tuple) make it viable for distributed teams.

## Engineering Knowledge
💡 **Engineering Knowledge — Mob Programming**: Whole team, one keyboard, one problem. The driver types; navigators direct. Rotate every 10 minutes. Sounds inefficient — it isn't for hard problems. Mobbing on the hardest problem of the sprint accelerates decision-making, transfers knowledge to the whole team simultaneously, and prevents the "brilliant jerk writes code nobody else understands" failure mode. Reserve it for the highest-complexity, highest-value work. → `engineering-knowledge-repository/methodologies/mob-programming.md`

## Related Entries
- [Pair Programming](pair-programming.md) — mob programming is pair programming scaled to the whole team
- [Test-Driven Development](test-driven-development.md) — TDD + mob programming is a powerful combination for complex domain logic

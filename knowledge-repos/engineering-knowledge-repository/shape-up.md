---
id: shape-up
tags: [methodology, team-practices]
surfaces-at: [requirements-analysis, user-stories]
related: [continuous-discovery, yagni-principle, definition-of-done]
complexity: intermediate
---

# Shape Up

## What It Is
A product development methodology from Basecamp (Jason Fried and David Heinemeier Hansson) that uses fixed-time, variable-scope cycles. Work is shaped into "pitches" that define the problem and appetite (how much time is worth spending) — not detailed specs. Small teams (1-2 engineers + designer) get 6-week cycles with full autonomy to solve the shaped problem. No backlogs, no estimation, no sprints.

## When to Apply
- Product teams that want to move away from perpetual backlog grooming and sprint ceremonies
- When detailed upfront specification leads to scope creep and missed deadlines
- Small, autonomous teams where centralized coordination overhead isn't warranted
- Organizations willing to commit to fixed time but variable scope

## When Not to Apply
- Client engagements with contractual scope commitments — Shape Up's variable scope is incompatible with fixed-scope contracts
- Large teams that require heavy coordination across many squads
- Regulated environments with mandatory documentation and approval gates that don't fit 6-week cycles
- Teams that need fine-grained progress visibility during a cycle

## Key Concepts
- **Appetite**: How much time a problem is worth — "this is a 2-week problem, not a 6-week problem." Constrains solution complexity.
- **Shaping**: The work done before the cycle to define the problem clearly, set boundaries, and leave the solution open enough for the team to own it
- **Betting Table**: Where shaped pitches are reviewed and selected — not a prioritized backlog
- **6-Week Cycle**: The build phase — no check-ins, no changes, the team owns the problem
- **Cooldown**: 2 weeks after each 6-week cycle for fixing bugs, exploring ideas, and shaping the next pitches
- **No Backlogs**: Unpitched work dies — if it's still important, someone will pitch it again. This prevents backlog debt.
- **Circuit Breaker**: If a problem isn't solved in the 6-week cycle, it doesn't automatically continue — it goes back to shaping

## In Practice
Shape Up is an alternative to Scrum/Kanban for product teams with strong ownership culture. Method recommends it for internal product work where the team has full control over scope definition. The most valuable concept for any engagement, regardless of methodology, is **appetite** — defining how much time a problem is worth before designing the solution, rather than estimating the solution and hoping it fits.

## Engineering Knowledge
💡 **Engineering Knowledge — Shape Up**: Instead of estimating tasks, define your appetite: how much is this problem worth? 2 weeks? 6 weeks? Then design a solution that fits. No backlogs — unworked ideas die; important ones get re-pitched. Teams get a full 6-week cycle with no interruptions. Even if you don't adopt Shape Up wholesale, the appetite concept is valuable in any methodology: decide how much time a problem deserves before you start designing the solution. → `engineering-knowledge-repository/methodologies/shape-up.md`

## Related Entries
- [Continuous Discovery](continuous-discovery.md) — continuous discovery feeds the shaping process with validated problem understanding
- [YAGNI Principle](../architectural-philosophy/yagni-principle.md) — appetite-based scoping is YAGNI in product methodology form

---
id: lean-software-development
tags: [methodology, team-practices]
surfaces-at: [requirements-analysis]
related: [continuous-discovery, shape-up, four-key-metrics, technical-debt-management, trunk-based-development]
complexity: intermediate
---

# Lean Software Development

## What It Is
The application of lean manufacturing principles — originating from the Toyota Production System — to software development. Popularized by Mary and Tom Poppendieck in *Lean Software Development: An Agile Toolkit* (2003). The core premise: eliminate waste (anything that doesn't add value to the customer), amplify learning, decide late, deliver fast, empower the team, build integrity in, and see the whole. Lean is not a process framework — it is a set of thinking tools that shape how teams make decisions.

## When to Apply
- When evaluating whether work items, processes, or meetings are adding value or adding waste
- When flow through the development process is slow and you want to identify bottlenecks
- When a team is drowning in partially-done work, context switching, or rework
- As a mental model for continuous improvement across any delivery framework (Scrum, Kanban, Shape Up)

## Key Concepts
- **The Seven Wastes of Software** (adapted from manufacturing):
  1. *Partially done work* — code not in production creates inventory that rots
  2. *Extra features* — building what wasn't asked for (YAGNI in practice)
  3. *Relearning* — not capturing knowledge; solving the same problems repeatedly
  4. *Handoffs* — every handoff loses information and adds delay
  5. *Task switching* — context switching between multiple work items reduces throughput
  6. *Delays* — waiting for approvals, reviews, environments, or decisions
  7. *Defects* — bugs discovered late are the most expensive waste

- **Value Stream Mapping**: Visualize the entire flow from idea to production — every step, wait time, and handoff. Waste becomes visible. Lead time vs. cycle time reveals where delays accumulate

- **Pull vs. Push**: Work is pulled by capacity (teams take work when ready) rather than pushed by schedules. WIP limits enforce this — no new work starts until current work finishes

- **WIP Limits (Work in Progress)**: Constraining the number of items in flight forces finishing over starting. Reduces context switching and reveals bottlenecks

- **Amplify Learning**: Shorten feedback loops at every level — CI, TDD, frequent releases, user interviews. The faster the feedback, the less waste from going in the wrong direction

- **Decide as Late as Possible**: Preserve optionality — make irreversible decisions as late as you can, when you have the most information. Not the same as procrastinating

- **Deliver as Fast as Possible**: Small batch sizes, trunk-based development, continuous deployment. Fast delivery reduces WIP, shortens feedback loops, and reduces risk per release

- **Respect for People**: Teams closest to the work have the best knowledge. Empower them to make decisions rather than escalating everything

## In Practice
Lean thinking is applied in Method engagements through: WIP limits in sprint boards, value stream mapping during retrospectives to identify delivery bottlenecks, minimizing handoffs between teams through cross-functional team structures, and treating partially-completed features (not in production) as inventory risk. Lean is the underlying rationale for trunk-based development, small PRs, feature flags, and continuous deployment.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Lean Software Development**: Eliminate waste before adding process. The seven wastes — partially done work, extra features, relearning, handoffs, task switching, delays, defects — are where your delivery time actually goes. Map your value stream: draw every step from idea to production and measure wait times. Impose WIP limits — finishing beats starting. Decide late (preserve options), deliver fast (small batches). Lean isn't a framework; it's a lens for seeing waste that other frameworks hide. → `engineering-knowledge-repository/lean-software-development.md`

## Related Entries
- [Continuous Discovery](continuous-discovery.md) — continuous user feedback amplifies learning, a core lean principle
- [Shape Up](shape-up.md) — Shape Up's appetite-based scoping is lean's "decide as late as possible" applied to product planning
- [Four Key Metrics](four-key-metrics.md) — DORA metrics measure lean flow: lead time and deployment frequency are direct waste indicators
- [Technical Debt Management](technical-debt-management.md) — unmanaged technical debt is defect waste and delays compounding over time
- [Trunk-Based Development](trunk-based-development.md) — daily integration eliminates the partially-done-work waste of long-lived branches

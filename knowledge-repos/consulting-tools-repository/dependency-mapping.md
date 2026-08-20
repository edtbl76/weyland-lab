---
id: dependency-mapping
tags: [delivery, organizational]
surfaces-at: [workflow-planning, validated-intent]
related: [safe, iron-triangle, risk-register, raci, moscow-prioritization]
complexity: intermediate
---

# Dependency Mapping

## What It Is
The practice of identifying, documenting, and managing the dependencies between work items, teams, systems, or external parties in a delivery program — establishing what must be done, decided, or delivered before something else can proceed. In software delivery, dependencies take multiple forms: technical dependencies (system A cannot be built until system B's API is stable), team dependencies (the mobile team is waiting for the backend team's data model), external dependencies (regulatory approval must precede go-live), and assumption dependencies (this work assumes a decision that hasn't been made). Unmanaged dependencies are the primary cause of delivery slippage in multi-team programs.

## When to Use
- Multi-team program planning: identifying cross-team dependencies before delivery begins
- SAFe PI Planning: the program board is a dependency map
- When a delivery program is slipping with unclear root cause — unresolved dependencies are usually visible in a mapping exercise
- Sequencing work: establishing the critical path and identifying which dependencies have schedule impact
- Risk management: dependencies with external parties or long lead times are program risks

## Key Concepts
- **Dependency Types**:
  - *Finish-to-Start (FS)*: B cannot start until A is finished. The most common type
  - *Finish-to-Finish (FF)*: B cannot finish until A is finished
  - *Start-to-Start (SS)*: B cannot start until A starts
  - *External Dependencies*: Outside the program's control — vendor deliveries, regulatory approvals, data migrations, client decisions
- **Dependency Register**: A structured artifact listing each dependency, the two parties involved (waiting team and providing team), the expected delivery date, current status, and risk level. Updated weekly in active programs
- **Critical Path**: The sequence of dependent tasks that determines the minimum project duration. Tasks on the critical path have zero float — any delay cascades to the program end date. Dependency mapping reveals the critical path
- **Dependency Visualization**:
  - *String Diagrams / Program Board*: Visual map showing team swimlanes across time with string (or arrows) connecting dependent items. Used in SAFe PI Planning
  - *Dependency Matrix*: Teams listed on both axes; cells indicate dependency direction. Useful for identifying teams with many dependencies (coupling risk)
  - *Network Diagram (PERT/CPM)*: Sequential task visualization with dependency arrows; reveals critical path
- **Dependency Risk Factors**: Lead time (long lead = high risk), external owner (outside program control = high risk), single point of failure (only one person can resolve = high risk), assumption dependencies (undecided = high risk)
- **Reducing Dependencies**: Dependencies can be redesigned out of a program through architecture decisions (decouple systems), team design (co-locate dependency pairs), or sequencing (batch dependent items into the same sprint). Reducing dependencies is often more effective than managing them

## Method Application
Method maps dependencies at the start of every multi-team engagement and maintains the dependency register throughout delivery. The dependency map is a standing agenda item in weekly program status meetings — not to review the list, but to identify new dependencies and resolve blocked ones. When a program is slipping, Method's first diagnostic is the dependency map: which dependencies are on the critical path and which are at risk?

## Consulting Insight
🎯 **Consulting Tool — Dependency Mapping**: The most impactful moment in a dependency mapping exercise is when a team realizes they have been waiting on something for three weeks that was never formally identified as a dependency. "We were blocked but we didn't know who to escalate to." Dependency mapping prevents this by making the wait visible before it becomes a slip. Run a dependency identification session with all teams in the first week of a multi-team program — the conversations it generates are more valuable than the artifact it produces. → `consulting-tools-repository/dependency-mapping.md`

## Related Entries
- [SAFe](safe.md) — SAFe's program board is a visual dependency map; PI Planning is a structured dependency identification and resolution session
- [Iron Triangle](iron-triangle.md) — critical path dependencies constrain schedule regardless of other triangle vertices
- [Risk Register](risk-register.md) — high-risk dependencies are direct inputs to the program risk register
- [RACI](raci.md) — RACI clarifies who is responsible and accountable for providing each dependency
- [MoSCoW Prioritization](moscow-prioritization.md) — Must Haves with unresolved dependencies may need to be re-categorized; dependencies determine feasibility, not just priority

---
id: iron-triangle
tags: [delivery, strategy]
surfaces-at: [validated-intent, workflow-planning, requirements-analysis]
related: [moscow-prioritization, dependency-mapping, risk-register, safe, decision-matrix]
complexity: foundational
---

# Iron Triangle (Project Management Triangle)

## What It Is
A foundational project management model that describes the interdependency between three constraints on any delivery program: Scope (what is delivered), Schedule (when it is delivered), and Cost (how much it costs). The model states that these three constraints are interdependent — changing one forces adjustment in at least one of the other two. The common formulation: "Good, Fast, Cheap — pick two." A fourth constraint, Quality, is sometimes added (the "diamond"), with quality at the center rather than as a fixed vertex. The Iron Triangle is a communication and governance tool, not a precise mathematical model — its value is making constraint trade-offs explicit before programs begin.

## When to Use
- Program scoping: establishing which constraint is fixed and which is flexible before committing to delivery
- Stakeholder alignment: surfacing implicit assumptions about what happens when scope changes
- Change control: evaluating the impact of a scope change request on schedule and cost
- When a client wants to expand scope without adjusting schedule or budget — the triangle makes the trade-off visible
- Communicating program constraints to executive stakeholders in accessible terms

## Key Concepts
- **The Three Vertices**:
  - *Scope*: The features, functionality, and quality of what is delivered
  - *Schedule*: The time available to deliver
  - *Cost*: The budget and resources available
- **Fixed vs. Flexible Constraints**: Every program has at least one fixed constraint (a hard launch date, a regulatory deadline, an immovable budget) and at least one flexible constraint. Identifying which is which at the start of a program prevents mid-delivery conflict
- **Agile and the Triangle**: In agile delivery, Scope is typically the flexible constraint — the team delivers the highest-value work within a fixed time and cost (sprint velocity). This is the fundamental difference from waterfall, where scope is fixed and time/cost flex
- **"Good, Fast, Cheap — Pick Two"**: The folk wisdom version. In practice, all three constraints are partly negotiable, and quality (the fourth dimension) is rarely truly tradeable — poor quality produces schedule and cost debt that exceeds the initial "savings"
- **Scope Creep**: The most common delivery failure mode — scope expands incrementally without corresponding schedule or cost adjustment. The triangle makes scope creep visible by forcing the question: "if we add this, what gives?"
- **Technical Debt as Cost**: In software delivery, technical debt can be understood as a hidden Scope or Cost reduction — teams "borrow" from future quality to meet present schedule. The triangle makes this trade-off explicit: "we can meet the schedule, but we'll carry this debt forward"
- **Stakeholder Communication**: The Iron Triangle is accessible to non-technical stakeholders in a way that detailed project plans are not. When an executive asks "why is this taking so long?", the triangle answer is: "we've fixed both schedule and scope — the only remaining lever is cost (adding resources), which has diminishing returns beyond this team size"

## Method Application
Method uses the Iron Triangle at program kickoff to establish with the client which constraint is fixed. This sets the terms of the change control process: scope changes require schedule or cost adjustment; schedule compression requires scope reduction or cost increase. Without this agreement at the start, every scope change becomes a negotiation rather than a governed trade-off.

## Consulting Insight
🎯 **Consulting Tool — Iron Triangle**: The Iron Triangle's most important question is: "which vertex is actually fixed?" In practice, clients often present all three as fixed — fixed scope, fixed date, fixed budget — which is a statement that the team must absorb all risk. Surfacing this conflict at the start of the program, rather than discovering it at the first scope change, is one of the most valuable services a consulting team can provide. The triangle gives you the language to have that conversation without it becoming adversarial. → `consulting-tools-repository/iron-triangle.md`

## Related Entries
- [MoSCoW Prioritization](moscow-prioritization.md) — MoSCoW operationalizes the scope vertex; when schedule is fixed, Must Haves define the minimum viable scope
- [Dependency Mapping](dependency-mapping.md) — dependencies constrain schedule regardless of the other triangle vertices
- [Risk Register](risk-register.md) — risks are threats to one or more triangle vertices; risk responses must be evaluated against triangle trade-offs
- [SAFe](safe.md) — SAFe's Program Increment planning makes the triangle explicit at the program level
- [Decision Matrix](decision-matrix.md) — when constraint trade-offs require a structured decision, a decision matrix evaluates options against triangle dimensions

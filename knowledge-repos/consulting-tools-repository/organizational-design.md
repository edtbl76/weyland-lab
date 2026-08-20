---
id: organizational-design
tags: [organizational, strategy]
surfaces-at: [validated-intent, requirements-analysis]
related: [mckinsey-7s, raci, adkar, capability-maturity-model, kotters-8-step]
complexity: advanced
---

# Organizational Design

## What It Is
The deliberate configuration of an organization's structures, roles, processes, and systems to enable strategy execution. Organizational design addresses how work is divided (specialization), how it is coordinated (integration mechanisms), how decisions are made (centralization vs. decentralization), and how people are grouped (functional, divisional, matrix, product-led, platform models). Effective organizational design aligns the organization's structure with its strategy — "structure follows strategy" (Chandler's principle). Technology transformation programs frequently require organizational redesign because digital capabilities require different team structures, decision-making models, and skills than the organizations they're transforming.

## When to Use
- When a technology transformation requires new team structures (e.g., moving from project to product model)
- Platform or operating model transformations that create new shared services or centers of excellence
- When an existing structure is blocking technology adoption or delivery speed
- M&A integration: designing the combined organization's structure
- When a client's strategy requires capabilities that the current structure cannot support

## Key Concepts
- **Design Dimensions**:
  - *Specialization*: How narrowly or broadly are roles defined? Deep specialization increases expertise; broad roles increase flexibility
  - *Integration*: How do specialized units coordinate? Mechanisms range from rules and procedures to cross-functional teams to integrating roles
  - *Centralization*: Where are decisions made? Centralized decisions enable consistency; decentralized decisions enable speed and local adaptation
  - *Formalization*: How much work is governed by explicit rules and processes vs. informal norms and judgment?
- **Common Structural Models**:
  - *Functional*: Organized by expertise (Engineering, Product, Design, Marketing). Enables deep specialization; creates coordination overhead across functions
  - *Divisional/Product*: Organized by product line or business unit. Enables focus and autonomy; creates duplication and inconsistency
  - *Matrix*: Dual reporting — functional expertise plus product/project authority. Enables both; creates accountability ambiguity (who do you really work for?)
  - *Platform/Enabling Team Model*: Inspired by Team Topologies — stream-aligned teams own product delivery; platform teams provide shared capabilities; enabling teams coach and uplift
- **Team Topologies**: Matthew Skelton and Manuel Pais's model for modern software team design — four team types (Stream-Aligned, Platform, Enabling, Complicated-Subsystem) with defined interaction modes (Collaboration, X-as-a-Service, Facilitating). Increasingly the reference model for technology organization design
- **Conway's Law**: "Organizations design systems that mirror their communication structures." Organizational boundaries become software architecture boundaries. To change the architecture, sometimes you must change the organization — or design the org with the target architecture in mind (Inverse Conway Maneuver)
- **Span of Control**: How many people report to each manager? Wider spans reduce management layers and cost; narrower spans increase support and development quality. Technology organizations typically support spans of 5-10
- **Change and Transition**: Organizational redesign is a major change management event — people lose roles, reporting relationships, and identity. ADKAR and Kotter interventions are required alongside structural changes

## Method Application
Method addresses organizational design in transformation programs where the existing structure is blocking strategy execution. When a client wants to move faster on digital delivery but runs all product decisions through a centralized PMO with 6-week approval cycles, the structural barrier must be redesigned alongside the technology investment. Method surfaces this at program kickoff and names it explicitly rather than trying to work around it.

## Consulting Insight
🎯 **Consulting Tool — Organizational Design**: The most common organizational design mistake in technology transformation is building the new technology on top of the old structure. You can deliver a modern platform and a new operating model, but if the teams using them are still organized around functions, governed by a project model, and measured on utilization rather than outcomes — the platform will underperform. Conway's Law is real. Design the organization you need before you finalize the architecture you're building. → `consulting-tools-repository/organizational-design.md`

## Related Entries
- [McKinsey 7-S](mckinsey-7s.md) — organizational design changes the Structure element of 7-S; must be aligned with Strategy, Systems, and Shared Values
- [RACI](raci.md) — organizational design establishes roles; RACI clarifies decision rights within those roles
- [ADKAR](adkar.md) — structural redesign requires individual change management; ADKAR structures the journey for each affected person
- [Capability Maturity Model](capability-maturity-model.md) — higher CMM maturity levels require defined structures; organizational design enables maturity progression
- [Kotter's 8-Step](kotters-8-step.md) — organizational redesign is often the content of a major Kotter change program; the same 8-step process applies

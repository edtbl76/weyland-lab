---
id: team-topologies
tags: [organizational, delivery, architecture, strategy]
surfaces-at: [requirements-analysis, workflow-planning, application-design]
related: [core-domain-chart, organizational-design, cynefin, dependency-mapping, raci, wardley-mapping, independent-service-heuristics]
complexity: intermediate
---

# Team Topologies

## What It Is
A framework for designing software delivery organizations based on team cognitive load, interaction modes, and flow optimization. Created by Matthew Skelton and Manuel Pais, and a central chapter in Nick Tune's *Architecture Modernization*. Team Topologies proposes four fundamental team types and three interaction modes as the building blocks for any delivery organization. The core insight is that org structure and system architecture are inseparable (Conway's Law) — and that most organizations are structured in ways that actively work against fast, sustainable software delivery. Cognitive load is a first-class design constraint: teams should be sized and scoped such that they can fully own their domain without being overwhelmed.

## When to Use
- When an organization's team structure is misaligned with its architecture (Conway's Law violations)
- During modernization engagements where the org structure needs to evolve alongside the technical architecture
- When delivery is slow and the root cause is team coupling, unclear ownership, or communication overhead
- When designing platform or enabling team strategies
- To challenge over-specialized team structures that create hand-offs and queues
- As a framework for discussing team cognitive load without it becoming a personal critique

## Key Concepts
- **Four Team Types**:
  - *Stream-aligned team*: Aligned to a flow of business value (a product, a user journey, a domain). Owns the full delivery lifecycle for its stream. This is the primary team type — all other types exist to reduce the cognitive load of stream-aligned teams.
  - *Platform team*: Provides a self-service internal platform that reduces cognitive load for stream-aligned teams. Does not deliver features directly to end users. Success is measured by how much it reduces the need for stream-aligned teams to deal with infrastructure, tooling, or cross-cutting concerns.
  - *Enabling team*: Short-lived team of specialists that helps stream-aligned teams acquire new capabilities (a new technology, a practice, a methodology). Goal is to make itself unnecessary — capability transfer, not dependency creation.
  - *Complicated-subsystem team*: Owns a component that requires deep specialist knowledge (ML models, cryptography, complex algorithms). Exists to protect stream-aligned teams from specialist complexity, not to gatekeep.
- **Three Interaction Modes**:
  - *Collaboration*: Two teams work closely together for a defined period to solve a shared problem. High-bandwidth but expensive — should be time-limited.
  - *X-as-a-Service*: One team consumes another's capability as a service with a published API. Low-bandwidth, scalable, but requires strong interface design.
  - *Facilitating*: An enabling team helps another team improve its practices. Temporary, capability-building.
- **Cognitive Load as a Design Constraint**: Every team has a cognitive load limit. Teams are too large when members can't maintain awareness of the full domain. Teams are too small when they can't own their domain without constant help. Team Topologies makes cognitive load an explicit design input, not an afterthought.
- **Conway's Law**: Organizations design systems that mirror their communication structure. Team Topologies operationalizes the inverse — Inverse Conway Maneuver: design the team structure to mirror the desired architecture, then let the architecture follow.
- **Team-first thinking**: Team Topologies reframes architecture decisions as team decisions. The question is not "what is the right microservice boundary?" but "what is the right team boundary?" — the service boundary follows from the team boundary.

## Method Application
Team Topologies is most applicable during Requirements Analysis and Workflow Planning when discussing how the client's organization will support the architecture being designed. Method engagements often identify Conway's Law violations — teams structured in ways that make the desired architecture impossible to maintain. Team Topologies provides the vocabulary and framework for proposing organizational changes alongside technical changes. It also directly informs Method's own engagement staffing: stream-aligned teams (per archetype), enabling functions (Design, Research), and platform thinking (harness engineering).

## Consulting Insight
🎯 **Consulting Tool — Team Topologies**: The most common architecture modernization failure is changing the system without changing the organization. A microservices architecture owned by a centralized operations team is a distributed monolith waiting to happen. Team Topologies gives you the language to make the org change argument alongside the architecture argument — and cognitive load gives you a non-political way to say "this team is trying to own too much." → `consulting-tools-repository/team-topologies.md`

## Solutions Context
Team Topologies is a powerful framing for scoping modernization engagements. When a client's team structure cannot support the target architecture, the engagement scope must include organizational change — not just technical delivery. This has implications for stakeholder management, change management, and timeline. Tangible Discovery engagements often surface Team Topologies violations that become the primary recommendation in the Phase N+1 brief.

## Related Entries
- [Core Domain Chart](core-domain-chart.md) — domain classification directly informs team type: Core Domains → stream-aligned teams; Generic Domains → platform or outsourced
- [Organizational Design](organizational-design.md) — broader organizational design framework; Team Topologies is the software-delivery-specific implementation
- [Cynefin](cynefin.md) — Cynefin's Complex domain requires team structures that can experiment; Team Topologies' stream-aligned teams are the right structure for Complex domain work
- [Dependency Mapping](dependency-mapping.md) — dependencies between teams are a Team Topologies design problem; high-dependency teams should move toward X-as-a-Service interaction
- [Wardley Mapping](wardley-mapping.md) — Wardley Map evolution stages inform team type: Genesis/Custom-Built → stream-aligned; Commodity → platform or outsource
- [Independent Service Heuristics](independent-service-heuristics.md) — the Team Topologies community's checklist for validating whether a proposed service boundary can be owned independently by a single team

---
id: conways-law
tags: [principle, team-practices, distributed-systems]
surfaces-at: [application-design, requirements-analysis]
related: [microservices, team-topologies, modular-monolith, domain-driven-design]
complexity: foundational
---

# Conway's Law

## What It Is
"Any organization that designs a system will produce a design whose structure is a mirror image of the organization's communication structure." — Melvin Conway, 1967. The implication: your architecture reflects your org chart whether you intend it to or not. Teams that don't communicate build systems that don't communicate. Teams with fuzzy boundaries build systems with fuzzy interfaces.

## When to Apply
- Planning service or module boundaries — align them with team ownership boundaries
- Diagnosing architectural coupling — trace it back to team coupling; fix the org, fix the architecture
- Scaling engineering organizations — new team boundaries should be drawn at natural system seams
- Evaluating proposed architectures — ask who owns each piece and whether the ownership model is sustainable

## When Not to Apply
- Conway's Law is descriptive, not prescriptive — it doesn't say what structure to adopt, only that structure will reflect communication patterns. Use it as a diagnostic, not a blueprint.

## Key Concepts
- **Inverse Conway Maneuver**: Deliberately design team structures to produce the desired system architecture — shape the org to drive the architecture rather than letting the architecture be an accidental byproduct
- **Team Topologies**: A framework (by Skelton & Pais) for deliberately designing team structures to enable fast flow — stream-aligned, platform, enabling, and complicated-subsystem teams
- **Communication Overhead**: Brooks' Law and Conway's Law are complementary — large teams with complex communication structures produce complex systems
- **Microservices and Org Structure**: Microservices decomposition should align with team boundaries. Services owned by the same team are often better as modules. Services that need different deployment cadences or separate ownership are candidates for service extraction.
- **Monolith as Communication Proxy**: A monolith owned by one team is fine. A monolith owned by five teams is a coordination nightmare — Conway's Law predicts the architecture will suffer.

## In Practice
Conway's Law is one of the most practically useful concepts in Method's architecture practice. When a client's monolith has unclear module boundaries, the root cause is almost always unclear team ownership. When a microservices system has services that are tightly coupled at runtime, it usually reflects two teams that are tightly coupled organizationally. The Inverse Conway Maneuver — designing teams first, then architecture — is an underused lever.

## Engineering Knowledge
💡 **Engineering Knowledge — Conway's Law**: Your architecture mirrors your org chart. Teams that don't communicate build systems that don't communicate. Before designing service boundaries, design team boundaries — the Inverse Conway Maneuver. A microservices architecture split along the wrong team lines will accumulate coupling faster than the monolith it replaced. Ask: who owns it, who deploys it, who's on call for it? Those answers define your real service boundary. → `engineering-knowledge-repository/architectural-philosophy/conways-law.md`

## Related Entries
- [Microservices](../architectural-styles/microservices.md) — service boundaries should align with team ownership per Conway's Law
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Bounded Contexts define natural team and service boundaries
- [Modular Monolith](../architectural-styles/modular-monolith.md) — module ownership reflects Conway's Law within a single deployment

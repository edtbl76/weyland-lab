---
id: team-topologies
tags: [reference, team-practices]
surfaces-at: [application-design, requirements-analysis]
related: [conways-law, microservices, developer-experience, inner-source, internal-developer-platform, golden-path]
complexity: intermediate
---

# Team Topologies

## What It Is
A framework for designing software delivery organizations, created by Matthew Skelton and Manuel Pais (book: *Team Topologies*, 2019). It defines four team types and three interaction modes that optimize for fast flow of value. The framework operationalizes Conway's Law: intentionally design team structures to produce the desired system architecture.

## When to Apply
- Scaling engineering organizations beyond a single team
- When team dependencies are slowing delivery — teams blocked on other teams for every release
- When designing a platform or internal developer tooling strategy
- When Conway's Law is producing the wrong architecture — org structure must change before architecture can

## When Not to Apply
- Very small organizations (1-3 teams) — the framework overhead isn't justified; optimize later
- Organizations where management won't act on team structure recommendations — architecture advice without org authority produces frustration

## Key Concepts
**Four Team Types:**
- **Stream-Aligned Team**: Aligned to a flow of business value (a product, feature area, or customer journey). Owns end-to-end delivery. The primary team type.
- **Platform Team**: Provides internal capabilities (CI/CD, infrastructure, shared services) as a product to stream-aligned teams. Reduces cognitive load on stream teams.
- **Enabling Team**: Specialists who help stream teams acquire new capabilities (security, UX, performance) temporarily — consult and leave, don't own.
- **Complicated-Subsystem Team**: Owns particularly complex subsystems requiring deep specialist knowledge — interfaces cleanly with stream teams.

**Three Interaction Modes:**
- **Collaboration**: Two teams work closely together for a defined period — high bandwidth, temporary
- **X-as-a-Service**: One team provides a service/platform; the other consumes it with minimal interaction
- **Facilitating**: An enabling team helps a stream team upskill, then steps back

**Cognitive Load**: A central concept — stream teams must be able to own their entire domain without being overwhelmed. Platform teams reduce cognitive load by abstracting infrastructure complexity.

## In Practice
Team Topologies is Method's framework for organizational recommendations in delivery engagements. The most common application: recommend a Platform team to provide CI/CD, environments, and shared observability infrastructure; allow stream-aligned teams to focus entirely on business features. The interaction mode recommendation (X-as-a-Service vs. Collaboration) defines how teams interface.

## Engineering Knowledge
💡 **Engineering Knowledge — Team Topologies**: Four team types: Stream-aligned (builds the product), Platform (provides internal infrastructure as a service), Enabling (upskills stream teams temporarily), Complicated-Subsystem (owns gnarly specialist components). The goal is fast flow: stream teams should be able to deliver independently without constant coordination with others. If your stream teams are blocked on other teams every sprint, your team topology is wrong. → `engineering-knowledge-repository/team-practices/team-topologies.md`

## Related Entries
- [Conway's Law](../architectural-philosophy/conways-law.md) — Team Topologies is the operational framework for applying the Inverse Conway Maneuver
- [Developer Experience](developer-experience.md) — Platform teams exist to improve developer experience for stream teams
- [Inner Source](inner-source.md) — inner source enables contribution across team boundaries in a Team Topologies model
- [Internal Developer Platform](internal-developer-platform.md) — platform teams build and maintain the IDP as their primary product for stream-aligned teams
- [Golden Path](golden-path.md) — the opinionated default path platform teams maintain to reduce stream-aligned team cognitive load

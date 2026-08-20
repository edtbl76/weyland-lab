---
id: independent-service-heuristics
tags: [ddd, architecture, facilitation, discovery]
surfaces-at: [requirements-analysis, application-design]
related: [team-topologies, core-domain-chart, domain-message-flow-modelling, event-storming, domain-storytelling, wardley-mapping]
complexity: intermediate
---

# Independent Service Heuristics

## What It Is
A lightweight checklist of ten questions — published by the Team Topologies community — for evaluating whether a candidate capability, domain, or product area could viably operate as an independent service or value stream. The heuristics are structured as a sense-check, not a scoring rubric: the questions stimulate conversation about feasibility, coupling, ownership, and cognitive load. The tool does not tell you *what* the service boundary should be; it surfaces whether the proposed boundary is defensible. Available at [github.com/TeamTopologies/Independent-Service-Heuristics](https://github.com/TeamTopologies/Independent-Service-Heuristics).

## When to Use
- When evaluating proposed bounded context or service boundaries after Event Storming or Domain Storytelling
- During Application Design when deciding whether to decompose a monolith into independently deployable services
- As a team exercise after a Core Domain Chart is drafted — apply the heuristics to Core Domain candidates before committing to service boundaries
- When a client proposes a microservices architecture: run the heuristics to validate whether each proposed service passes the independence test
- To de-politicize service boundary debates — the heuristics provide a shared, external frame that is not one person's opinion

## Key Concepts
- **The Ten Heuristics**: Each asks whether the candidate capability could viably stand alone:
  1. *Sense-check* — Is it logically feasible to operate this independently?
  2. *Brand* — Could it be marketed as a standalone cloud service?
  3. *Revenue / Customers* — Could it generate recurring revenue with identifiable customers?
  4. *Cost tracking* — Can costs and investment be measured separately?
  5. *Data* — Are input data sources clearly defined and independent?
  6. *User Personas* — Does it serve well-defined, distinct user types?
  7. *Teams* — Could a team build and operate it with bounded cognitive load?
  8. *Dependencies* — Can the owning team work autonomously most of the time?
  9. *Impact / Value* — Does it provide meaningful, recognizable value on its own?
  10. *Product Decisions* — Can the team own its own roadmap independently?
- **Conversation Frame, Not Scorecard**: A candidate that fails two or three heuristics is not automatically wrong — it is a signal to investigate those dimensions more deeply. The value is in the conversation the failures produce.
- **Anti-Patterns Surfaced**: The heuristics are particularly effective at exposing two common architecture mistakes: *data coupling* (the candidate shares a data store so tightly it cannot be deployed independently) and *forced release coordination* (the candidate cannot ship without synchronizing with multiple other teams).
- **Wardley Map Integration**: Heuristic 3 (outsourcing potential) aligns directly with Wardley Map evolution stages — a commodity capability that scores well on the heuristics is a strong candidate for platform or buy, not build.
- **Cognitive Load Check**: Heuristic 7 (Teams) is the Team Topologies cognitive load test applied to service boundaries. A candidate that a single team cannot own without being overwhelmed is either too large or too coupled to existing capabilities.

## Method Application
Independent Service Heuristics is most useful during Application Design after domain boundaries have been proposed. Run the heuristics as a structured team exercise: for each proposed service, work through all ten questions as a group. Services that fail heuristics 7 (Teams) or 8 (Dependencies) are the highest-priority redesign candidates — they will produce delivery bottlenecks regardless of how clean the code is. The heuristics are also effective as a boundary audit in Tangible Discovery engagements: apply them to the client's existing service inventory to identify which services are genuinely independent vs. which are distributed monolith segments in disguise.

## Consulting Insight
🎯 **Consulting Tool — Independent Service Heuristics**: The most common mistake in microservices design is drawing service boundaries based on technical components rather than independent value delivery. The ISH forces the question from the other direction: "Could this actually stand alone?" A proposed service that cannot pass heuristics 8 (Dependencies) and 7 (Cognitive Load) is not a service — it is a deployment unit that has inherited all the coupling of the monolith it replaced. The ISH is the fastest way to stress-test a client's proposed architecture before the team commits to building it. → `consulting-tools-repository/independent-service-heuristics.md`

## Related Entries
- [Team Topologies](team-topologies.md) — ISH is the Team Topologies community's boundary-testing tool; heuristic 7 is the cognitive load test from Team Topologies applied to service design
- [Core Domain Chart](core-domain-chart.md) — Core Domain classification informs which candidates to run through the heuristics; Core Domains should pass; Generic Domains may not need to
- [Domain Message Flow Modelling](domain-message-flow-modelling.md) — downstream: message flow models validate that proposed service boundaries produce acceptable coupling patterns
- [Event Storming](event-storming.md) — upstream: Event Storming surfaces candidate bounded contexts; ISH validates whether those candidates are viable as independent services
- [Domain Storytelling](domain-storytelling.md) — upstream: Domain Storytelling surfaces business processes; ISH evaluates whether those processes map to independently operable units
- [Wardley Mapping](wardley-mapping.md) — ISH heuristic 3 (outsourcing potential) maps directly to Wardley evolution stage; Commodity candidates should outsource rather than build

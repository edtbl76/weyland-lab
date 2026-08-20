---
id: event-storming
tags: [discovery, facilitation]
surfaces-at: [requirements-analysis, application-design]
related: [service-blueprinting, contextual-inquiry, wardley-mapping, how-might-we, affinity-mapping, independent-service-heuristics]
complexity: intermediate
---

# Event Storming

## What It Is
A collaborative domain modeling workshop technique developed by Alberto Brandolini that uses color-coded sticky notes on a large surface to map the domain events, commands, actors, and systems of a business process or software domain. Event Storming makes implicit domain knowledge explicit through structured conversation — business experts and developers build a shared model together, identifying domain events (things that happened), commands (actions that cause events), aggregates (the entities that own the business rules), policies (automated or human decisions), and external systems. The output is a domain model that both business and engineering teams understand and agree on.

## When to Use
- Domain discovery at the start of a complex software program — before any architecture or design decisions
- When business and engineering teams have poor shared understanding of the domain
- Identifying bounded contexts for microservices decomposition
- Uncovering business rules, edge cases, and exception flows that stakeholders haven't explicitly stated
- When event-driven architecture or CQRS/event sourcing is being considered

## Key Concepts
- **Domain Events (Orange)**: Things that happened in the domain — past tense, business-meaningful. "Order Placed", "Payment Processed", "Claim Approved". These are the backbone of the model and are identified first
- **Commands (Blue)**: Actions that cause domain events — present imperative. "Place Order", "Process Payment", "Approve Claim". Commands are what actors ask the system to do
- **Actors (Yellow)**: The people or personas who issue commands — customer, claims adjuster, system administrator
- **Aggregates (Yellow, larger)**: The domain entities that enforce business rules and process commands. In DDD terms, the consistency boundary. Aggregates emerge from clustering commands and events that belong together
- **Policies (Lilac)**: Reactive rules — "whenever X happens, then Y". Automated policies are business rules the system enforces; manual policies are human decision points. Policies are often where the most complex requirements live
- **External Systems (Pink)**: Third-party systems, APIs, or other bounded contexts that interact with the domain. Surfaces integration requirements
- **Hotspots (Red)**: Areas of disagreement, confusion, or risk — flagged in real time during the workshop for follow-up. Hotspots are as valuable as the model itself
- **Workshop Phases**: Big Picture Event Storming (full domain exploration, 2-4 hours) → Process Modeling (zoom into specific flows, identify aggregates and policies) → Software Design (map to system components and bounded contexts)
- **Big Paper Requirement**: Event Storming requires a physical or virtual surface large enough to lay out the full timeline. Space constraints are a real facilitation challenge; the timeline cannot be folded into a short wall

## Method Application
Method uses Event Storming at the start of complex domain-driven delivery programs — particularly where microservices or event-driven architectures are planned. It replaces months of requirements documentation with a one-day workshop that produces both the domain model and the alignment. The hotspot inventory from the workshop becomes the input to the requirements analysis deep-dive.

## Consulting Insight
🎯 **Consulting Tool — Event Storming**: The most valuable outcome of Event Storming is not the diagram — it's the conversation. When a business expert says "wait, that event can't happen before this one" and a developer says "but the system currently processes them in parallel," you've found a real defect in the current system and a genuine requirements clarification in the same moment. These conversations happen in event storming sessions because the shared visual makes inconsistencies visible in a way that documents and meetings do not. → `consulting-tools-repository/event-storming.md`

## Related Entries
- [Service Blueprinting](service-blueprinting.md) — event storming maps the system domain; service blueprinting maps the operational delivery layer; they complement each other
- [Contextual Inquiry](contextual-inquiry.md) — field observations from contextual inquiry provide the domain event evidence that makes Event Storming accurate
- [Wardley Mapping](wardley-mapping.md) — aggregates and bounded contexts from Event Storming can be positioned on a Wardley map to inform build/buy decisions
- [How Might We](how-might-we.md) — hotspots from Event Storming become HMW questions for solution ideation
- [Affinity Mapping](affinity-mapping.md) — hotspot clusters from Event Storming can be synthesized through affinity mapping before prioritization
- [Independent Service Heuristics](independent-service-heuristics.md) — downstream: bounded contexts identified in Event Storming are stress-tested through ISH before becoming committed service boundaries

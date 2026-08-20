---
id: event-storming
tags: [methodology, team-practices, backend]
surfaces-at: [application-design, functional-design]
related: [domain-driven-design, event-driven-architecture, event-sourcing, user-stories, rfcs-and-design-docs]
complexity: intermediate
---

# Event Storming

## What It Is
A collaborative workshop technique for rapidly exploring complex business domains by mapping domain events on a shared timeline. Participants — developers, domain experts, product managers — together place sticky notes representing domain events ("Order Placed", "Payment Failed", "Invoice Generated") in temporal order on a long horizontal surface (a wall or virtual whiteboard). The result is a shared understanding of the domain's event flow, surfacing business rules, aggregates, bounded contexts, and integration points that might take weeks to uncover through formal requirements gathering. Event Storming was created by Alberto Brandolini as a faster, more engaging alternative to traditional requirements workshops.

## When to Apply
- Discovering the domain model for a new system before design begins
- Onboarding a new team onto a complex, poorly-understood domain
- Identifying bounded contexts before decomposing a monolith into services
- When a team has misaligned mental models about what the system does
- At the start of a greenfield engagement to align business and engineering on domain vocabulary

## Key Concepts
- **Domain Events**: The core building block — something that happened in the system, expressed in past tense ("Payment Processed", "Subscription Cancelled"). Events represent facts; they are immutable and business-meaningful
- **Workshop Phases**: Event Storming typically runs in three progressive phases:
  1. *Big Picture Event Storming*: Rapid, chaotic event generation — everyone places events without structure. Surfacing the full timeline of the domain
  2. *Process Modeling*: Organize events into causal flows; add commands (what triggers the event), actors (who issues the command), and policies (automatic reactions to events)
  3. *Software Design*: Identify aggregates (stateful entities that enforce business rules), bounded contexts, and service boundaries
- **Notation Elements**:
  - Orange sticky: Domain event ("Order Shipped")
  - Blue sticky: Command ("Ship Order")
  - Yellow sticky: Actor/User ("Warehouse Manager")
  - Purple sticky: Policy ("When Order Shipped, send confirmation email")
  - Pink sticky: External system
  - Yellow large: Aggregate
- **Bounded Context Discovery**: Hot spots (areas of confusion, multiple competing models) reveal where bounded context boundaries should be drawn. One of the most valuable outputs of Event Storming is identifying these boundaries
- **Hotspots**: Red stickies mark areas of confusion, disagreement, or missing knowledge. Hotspots become the agenda for follow-up discovery
- **Virtual Event Storming**: Works in Miro, FigJam, or Mural. Less effective than in-person (physical movement and energy drive engagement), but workable. Use separate frames for each phase. Keep sessions to 2-3 hours maximum
- **Output**: The primary output is shared understanding, not a formal document. Photographs of the board, a cleaned-up Miro board, or a narrative summary capture the output. Formal artifacts (domain model, bounded context diagram) can be generated afterward

## In Practice
Method uses Event Storming at the start of complex domain engagement scopes — typically as a half-day or full-day workshop with both client domain experts and the engineering team. The workshop output feeds directly into bounded context identification, which informs service decomposition in application design. Virtual sessions use Miro with a pre-configured Event Storming template. Hotspots from the session become open questions in the requirements document.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Event Storming**: A 4-hour Event Storming workshop with the right people in the room produces more accurate domain understanding than 2 weeks of document-based requirements gathering. The key is including actual domain experts (not just product managers) — people who know what "Order Placed" really means in the business. The output is shared vocabulary and discovered boundaries, not a formal spec. Hotspots are features, not bugs — they reveal the hardest parts of the domain where upfront investment in clarity pays off. → `engineering-knowledge-repository/event-storming.md`

## Related Entries
- [Domain-Driven Design](domain-driven-design.md) — Event Storming is the primary workshop technique for DDD domain exploration
- [Event-Driven Architecture](event-driven-architecture.md) — events discovered in Event Storming become the events in an event-driven system
- [Event Sourcing](event-sourcing.md) — event flows mapped in Event Storming often map to event-sourced aggregates
- [User Stories](user-stories.md) — Event Storming sessions produce domain context that informs user story writing
- [RFCs and Design Docs](rfcs-and-design-docs.md) — bounded context decisions from Event Storming are documented in ADRs or RFCs

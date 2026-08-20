---
id: domain-message-flow-modelling
tags: [ddd, architecture, discovery]
surfaces-at: [requirements-analysis, application-design]
related: [core-domain-chart, event-storming, domain-storytelling, dependency-mapping, service-blueprinting, independent-service-heuristics]
complexity: intermediate
---

# Domain Message Flow Modelling

## What It Is
A lightweight visual modelling technique created by Nick Tune for mapping how commands, events, and queries flow between domains in a distributed system. It sits between Event Storming (broad exploration of the business domain) and detailed API or integration design (technical specification). A Domain Message Flow Model shows which domains produce which messages, which domains consume them, and what the trigger conditions are — making cross-domain dependencies visible without requiring full technical design. Featured prominently in *Architecture Modernization*.

## When to Use
- After domain boundaries have been identified (via Event Storming or Core Domain Chart) and before detailed service design
- When designing a modernized architecture with multiple domains or services that need to communicate
- To identify coupling: if two domains exchange too many messages, they may need to be merged or the boundary reconsidered
- During integration engagements where the flow between systems needs to be understood before API or event contracts are defined
- To facilitate cross-team conversations — the model is accessible to non-engineers (product, business) while still being technically meaningful

## Key Concepts
- **Messages**: The unit of communication between domains. Messages are typed as Commands (requests for action), Events (facts that happened), or Queries (requests for data). Each message type carries different coupling implications.
- **Producers and Consumers**: Each domain either produces or consumes messages. A domain that only produces events is loosely coupled; a domain that both produces and consumes commands from many others is tightly coupled and often a candidate for decomposition.
- **Flow Diagrams**: The model is typically a box-and-arrow diagram where boxes are domains (or bounded contexts) and arrows are labeled messages. Directionality is explicit — you can read coupling directly from the diagram.
- **Command vs. Event semantics**: Commands imply authority — the sender is telling the receiver to do something, and the receiver must comply. Events are announcements — the sender declares what happened; consumers decide what to do. Systems with too many Commands between domains are more brittle than systems built on Events.
- **Identifying Coupling**: Bidirectional message flows between domains are a red flag. Domains that cannot be changed without notifying multiple other domains are over-coupled and carry high modernization risk.
- **Not a sequence diagram**: Domain Message Flow Models show logical flow, not execution sequence or temporal ordering. For detailed interaction design, sequence diagrams follow.

## Method Application
Used during Application Design to validate domain boundaries identified in Requirements Analysis. If the message flow between two proposed domains is dense and bidirectional, the boundary is likely wrong. If one domain receives commands from every other domain, it is a bottleneck and should be reconsidered. The model is a fast, collaborative artifact — teams can sketch it on a whiteboard or Miro in hours, not days.

## Consulting Insight
🎯 **Consulting Tool — Domain Message Flow Modelling**: The most valuable thing this technique surfaces is hidden coupling. A client's proposed microservices architecture may look clean on an org chart but become a distributed monolith the moment you draw the message flows — where every service calls every other service and none can be deployed independently. Domain Message Flow Modelling makes that coupling visible before it is built, when it is cheap to fix. → `consulting-tools-repository/domain-message-flow-modelling.md`

## Related Entries
- [Core Domain Chart](core-domain-chart.md) — classifies domains before flows are mapped; Core Domains should have the cleanest, most autonomous flows
- [Event Storming](event-storming.md) — upstream: Event Storming surfaces the events and commands that become the messages in this model
- [Domain Storytelling](domain-storytelling.md) — alternative upstream technique for surfacing domain interactions
- [Dependency Mapping](dependency-mapping.md) — broader dependency visualization; Domain Message Flow Modelling is the DDD-specific version for message-based systems
- [Service Blueprinting](service-blueprinting.md) — complementary: Service Blueprinting maps human touchpoints; Domain Message Flow Modelling maps system-to-system communication
- [Independent Service Heuristics](independent-service-heuristics.md) — upstream validation: ISH checks whether proposed domains can be independently owned before message flows are designed

---
id: context-mapping
tags: [pattern, backend, methodology]
surfaces-at: [application-design]
related: [domain-driven-design, event-storming, microservices, conways-law]
complexity: intermediate
---

# Context Mapping

## What It Is
A DDD (Domain-Driven Design) technique for visualizing and managing the relationships between bounded contexts in a system. A context map is a diagram that shows how different bounded contexts (each with its own domain model and ubiquitous language) interact, integrate, and influence each other. Beyond a simple diagram, context mapping defines the organizational and technical relationship patterns between teams — including who has power in the relationship, whose model takes precedence, and how translation between models is handled. Created by Eric Evans in "Domain-Driven Design", context mapping is the tool for managing the complexity that arises when multiple domain models must coexist.

## When to Apply
- Designing integrations between multiple bounded contexts or services
- Before decomposing a monolith into microservices — context maps reveal natural seam lines
- When two teams have different domain models for the same real-world concept (e.g., "Order" means different things in fulfillment vs. billing)
- Identifying where anti-corruption layers are needed to prevent model pollution
- During Event Storming process modeling, when bounded context boundaries are being identified

## Key Concepts
- **Bounded Context**: A logical boundary within which a specific domain model applies and terms have unambiguous definitions. Inside a bounded context, "Customer" means one thing; in an adjacent context, "Customer" may mean something different. Context mapping manages the translation between them
- **Relationship Patterns**:
  - *Shared Kernel*: Two teams share a subset of their domain model. Changes require coordination between teams. High coupling; used when shared model is small and stable
  - *Customer-Supplier*: The upstream (supplier) context provides data/services; the downstream (customer) context consumes. The supplier has power; the customer adapts. Common in microservices
  - *Conformist*: Downstream fully conforms to the upstream model, even if it's suboptimal. Used when the upstream team is external or unwilling to coordinate (SaaS vendors, legacy systems)
  - *Anti-Corruption Layer (ACL)*: The downstream team builds a translation layer that converts the upstream model into its own language. Protects the downstream model from upstream model pollution. The appropriate choice when the upstream model is poor or when tight coupling is undesirable
  - *Open Host Service*: The upstream team publishes a formal protocol (API, event schema) that multiple downstream teams use. Reduces coupling; upstream makes breaking changes explicit
  - *Published Language*: A well-documented shared language (often a schema standard like FHIR in healthcare) that multiple contexts use. Enables integration without direct team coupling
  - *Separate Ways*: Two contexts have no meaningful integration — they solve completely different problems. No translation needed
- **Upstream/Downstream**: In the Customer-Supplier pattern, the upstream context influences (or determines) the downstream context's model. Understanding directionality is essential for identifying who has the integration burden
- **Anti-Corruption Layer (ACL)**: The most important defensive pattern. When integrating with a poorly-designed upstream model or external system, build an ACL that translates external concepts into your domain language. Prevents "legacy rot" from infecting your clean domain model
- **Context Map as Org Chart Reflection**: Conway's Law predicts that context boundaries will mirror team boundaries. Context mapping often reveals organizational tensions — shared kernels that require cross-team coordination, conformist relationships that mean one team is blocked by another

## In Practice
Method draws context maps at the start of complex domain decomposition engagements. The context map is an output of Event Storming process modeling. Anti-corruption layers are standard practice for integrating with client legacy systems — the ACL translates legacy data models into Method's service's domain model. Customer-Supplier relationships are explicitly documented in ADRs to record who is upstream and what the integration contract is.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Context Mapping**: Context mapping makes the often-implicit team and integration dynamics explicit: who depends on whom, whose model takes precedence, and where translation work lives. The most valuable insight from a context map is usually where the anti-corruption layers should go — identifying the integration points where you'd otherwise absorb a legacy or external model directly into your clean domain. Draw the map before designing the integration; discover the organizational tensions (shared kernels, conformist relationships) before they appear as architectural bottlenecks. → `engineering-knowledge-repository/context-mapping.md`

## Related Entries
- [Domain-Driven Design](domain-driven-design.md) — context mapping is a core DDD practice for managing multiple bounded contexts
- [Event Storming](event-storming.md) — Event Storming process modeling identifies bounded context boundaries that the context map formalizes
- [Microservices](microservices.md) — context map relationships inform microservice integration patterns and team ownership boundaries
- [Conway's Law](conways-law.md) — context map relationships often mirror team structures; understanding Conway's Law informs context boundary decisions

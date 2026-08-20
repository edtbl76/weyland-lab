---
id: distributed-monolith
tags: [anti-pattern, distributed-systems, microservices]
surfaces-at: [application-design]
related: [microservices, modular-monolith, domain-driven-design, service-mesh, evolutionary-architecture, conways-law]
complexity: intermediate
---

# Distributed Monolith

## What It Is
An anti-pattern where a system has been decomposed into multiple deployed services but retains the tight coupling and synchronous dependencies of a monolith — getting the operational complexity of microservices without the independence benefits. In a distributed monolith, services cannot be deployed, scaled, or developed independently because they are deeply coupled: Service A synchronously calls Service B which synchronously calls Service C, so a change to one requires coordinated changes to all, and a failure in any brings down the chain. The system appears distributed on the deployment diagram but behaves like a monolith in practice.

## How to Recognize It
- **Synchronized deployments**: Services must be deployed together because one depends on a specific version of another's API
- **Synchronous chains**: A user request triggers a chain of synchronous service calls (A → B → C → D) where latency adds up and any failure propagates
- **Shared databases**: Multiple services read and write the same database tables, creating implicit coupling through data
- **Chatty inter-service communication**: Services make dozens of calls to each other to serve a single user request — a network-call-heavy version of a single in-process method chain
- **Cross-service transactions**: Business logic requires coordinated writes across multiple services, often implemented with distributed transactions that are fragile and hard to reason about

## Key Concepts
- **Root Causes**: Distributed monoliths emerge from:
  - Decomposing a monolith by technical layer (service-per-layer) rather than by domain boundary (service-per-domain)
  - Not defining bounded contexts before decomposing — services end up with overlapping domains and shared data
  - Replicating monolith call patterns in distributed form — in-process function calls become synchronous HTTP calls
  - Organizational pressure to show architectural progress through service count rather than team autonomy
- **Why It's Worse Than a Monolith**: A well-built monolith has lower operational overhead, simpler debugging, transactional consistency, and faster local development than a distributed monolith. A distributed monolith has all the operational complexity of microservices (service discovery, network failures, observability, deployment coordination) with none of the independence benefits
- **The Fix — Domain Boundaries First**: Decompose along domain-driven design bounded contexts, not technical layers. Each service should own its data and domain logic; other services don't call into its database or depend on its internal model
- **Async Where Possible**: Replace synchronous service chains with asynchronous event-driven communication where latency and consistency requirements allow. Service A publishes an event; Service B reacts asynchronously. This decouples deployment and failure domains
- **Team Autonomy as a Test**: The test for a good microservices boundary: can one team deploy their service without coordinating with another team? If the answer is "no, they need to also update Service B's contract", the boundary is wrong
- **Modular Monolith First**: If starting greenfield, consider a modular monolith — a single deployable unit with strong module boundaries — before splitting into services. Extract services when a module has independent scaling, deployment, or team ownership needs, not as a first architecture decision

## In Practice
Method architecture reviews flag distributed monolith symptoms: synchronized deployment schedules, N+1 synchronous service call chains, shared database tables across services. Remediation starts with identifying the tightest coupling points and introducing asynchronous communication or merging services that share data back into a single service. Domain-driven design workshops (Event Storming) are used to identify correct service boundaries before further decomposition.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Distributed Monolith**: A distributed monolith is the worst of both worlds — you pay microservices' operational tax (network calls, service discovery, distributed tracing, multi-service debugging) without receiving the benefits (independent deployments, team autonomy, fault isolation). The cause is almost always decomposing by technical layer (API service, business logic service, data service) instead of by domain boundary. The fix is not to add more services — it's to merge tightly coupled services back together and redraw boundaries along domain lines. When in doubt, start with a modular monolith and extract services only when team autonomy or independent scaling genuinely requires it. → `engineering-knowledge-repository/distributed-monolith.md`

## Related Entries
- [Microservices](microservices.md) — microservices done correctly achieve team autonomy; a distributed monolith fails to achieve this
- [Modular Monolith](modular-monolith.md) — a better starting point than premature service decomposition; extract services when genuinely needed
- [Domain-Driven Design](domain-driven-design.md) — DDD bounded contexts provide the principled basis for correct service decomposition
- [Evolutionary Architecture](evolutionary-architecture.md) — evolutionary architecture advocates decomposing incrementally, avoiding big-bang microservices migrations
- [Conway's Law](conways-law.md) — distributed monoliths often reflect Conway's Law — technical layer teams produce technical layer services, not domain services

---
id: microservices
tags: [pattern, distributed-systems, backend, microservices]
surfaces-at: [application-design, nfr-requirements, infrastructure-design]
related: [modular-monolith, event-driven-architecture, cqrs, circuit-breaker, contract-testing, domain-driven-design, api-gateway-pattern]
complexity: intermediate
---

# Microservices

## What It Is
An architectural style where a system is composed of small, independently deployable services — each responsible for a specific business capability, owning its own data, and communicating over a network. Each service can be developed, deployed, and scaled independently.

## When to Apply
- Large organizations where multiple teams need to deploy independently without coordinating releases
- Systems with genuinely different scaling requirements across business capabilities
- When parts of the system have very different technology requirements
- When organizational boundaries (Conway's Law) naturally align with service boundaries

## When Not to Apply
- Small teams — the operational overhead of microservices is not justified below a certain team size (a common threshold: fewer than 3-4 teams)
- Early-stage products where boundaries are not yet understood — start with a modular monolith
- When the distributed systems complexity (network failures, data consistency, observability) would overwhelm the team
- "Microservices" defined by technical layers (a service per database table) rather than business capabilities

## Key Concepts
- **Single Business Capability**: Each service owns one business capability end-to-end — not a technical layer
- **Independent Deployability**: Services can be deployed without coordinating with other services
- **Own Your Data**: Each service owns its database — no shared databases across services
- **Smart Endpoints, Dumb Pipes**: Business logic lives in services; infrastructure (queues, gateways) is just transport
- **Conway's Law**: Systems reflect the communication structure of the organizations that build them. Align service boundaries with team boundaries.
- **Distributed Systems Tax**: Network latency, partial failure, data consistency, observability — these are the costs of microservices. They are real.

## In Practice
Method's default for greenfield projects is a **modular monolith first** — establish boundaries in code before establishing them across the network. Microservices are introduced when independent deployability or scaling becomes a genuine need, not as a starting point. The business capability boundaries discovered through DDD Bounded Contexts become the service boundaries when decomposition is warranted.

## Engineering Knowledge
💡 **Engineering Knowledge — Microservices**: Microservices solve an organizational scaling problem, not a technical one. You pay with distributed systems complexity — network failures, eventual consistency, observability overhead. Before decomposing, ask: do we have multiple teams that need to deploy independently? If not, a modular monolith delivers the same boundaries with far less complexity. → `engineering-knowledge-repository/architectural-styles/microservices.md`

## Related Entries
- [Modular Monolith](modular-monolith.md) — the recommended starting point before microservices
- [Domain-Driven Design](../methodologies/domain-driven-design.md) — Bounded Contexts define service boundaries
- [Event-Driven Architecture](event-driven-architecture.md) — the preferred integration pattern for microservices
- [Circuit Breaker](../infrastructure/circuit-breaker.md) — essential resilience for inter-service calls
- [Contract Testing](../testing/contract-testing.md) — validates service contracts without integration environments
- [API Gateway Pattern](api-gateway-pattern.md) — the standard entry point for microservices systems

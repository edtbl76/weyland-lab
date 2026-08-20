---
id: evolutionary-architecture
tags: [principle, backend, distributed-systems]
surfaces-at: [application-design, nfr-requirements]
related: [strangler-fig, event-driven-architecture]
complexity: intermediate
---

# Evolutionary Architecture

## What It Is
An architectural approach that treats change as a first-class concern. Rather than designing a system to be "correct" upfront, Evolutionary Architecture designs for guided change — using fitness functions to protect important characteristics as the system evolves over time. Coined by Neal Ford, Rebecca Parsons, and Patrick Kua.

## When to Apply
- Long-lived systems that will grow and change over years
- Systems where requirements are partially unknown or will emerge
- When the team values preserving architectural characteristics (performance, security, scalability) as the codebase grows
- Greenfield systems where you want to build in adaptability from the start

## When Not to Apply
- Short-lived systems with a fixed, known lifespan
- Throwaway prototypes or MVPs that will be discarded (not evolved)
- When the team lacks the discipline to maintain fitness functions over time

## Key Concepts
- **Fitness Function**: An objective, automated test for an architectural characteristic. Examples: "response time must stay under 200ms", "no direct database calls from the API layer", "test coverage must not drop below 80%". Fitness functions run in CI — they fail the build if the architecture degrades.
- **Incremental Change**: Prefer many small changes over infrequent large ones. Small changes are easier to reason about, test, and roll back.
- **Appropriate Coupling**: Not all coupling is bad. Evolutionary Architecture distinguishes between coupling that should be protected and coupling that should be eliminated.
- **Last Responsible Moment**: Defer architectural decisions until you have enough information — but no later. Avoid speculative generality.

## In Practice
Evolutionary Architecture shapes NFR Requirements — fitness functions are how non-functional requirements stay enforced as the codebase grows, not just documented and forgotten. During Application Design, it encourages designing component boundaries that can be changed later (especially relevant for the monolith → microservices evolution path). On brownfield engagements, it provides a framework for modernizing without big-bang rewrites.

## Engineering Knowledge
💡 **Engineering Knowledge — Evolutionary Architecture**: Architecture degrades under change unless you protect it actively. Consider defining fitness functions for your key NFRs — automated checks that run in CI and fail if architectural characteristics drift. Design for change, not just for today. → `engineering-knowledge-repository/architectural-philosophy/evolutionary-architecture.md`

## Related Entries
- [Strangler Fig](../infrastructure/strangler-fig.md) — the canonical Evolutionary Architecture pattern for legacy modernization
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — event-driven systems are naturally more evolvable

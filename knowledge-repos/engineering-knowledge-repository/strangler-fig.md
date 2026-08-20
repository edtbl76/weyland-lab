---
id: strangler-fig
tags: [pattern, backend, methodology]
surfaces-at: [infrastructure-design]
related: [evolutionary-architecture, circuit-breaker, event-driven-architecture]
complexity: intermediate
---

# Strangler Fig Pattern

## What It Is
An incremental migration pattern for replacing legacy systems. Rather than a big-bang rewrite, new functionality is built alongside the old system. A facade (the "strangler") intercepts requests and routes them to either the old system or the new one. Over time, more routes shift to the new system until the old one can be decommissioned — strangled out of existence, like the strangler fig tree. Coined by Martin Fowler.

## When to Apply
- Legacy system modernization where a big-bang rewrite is too risky
- When you need to deliver value incrementally while migrating
- Systems where you can introduce a routing layer or proxy in front of the legacy system
- When the legacy system cannot be taken offline for extended periods

## When Not to Apply
- Greenfield systems — there is nothing to strangle
- Systems where introducing a facade is technically infeasible (deeply embedded, no clear interface boundary)
- Very small legacy systems where a direct replacement is lower risk than building parallel infrastructure

## Key Concepts
- **Facade / Proxy**: The routing layer that intercepts requests and decides old vs new. Can be an API gateway, reverse proxy, or application-level router.
- **Event Interception**: For event-driven systems, intercept events and replay them to the new system during migration
- **Dark Launch / Shadow Mode**: Route traffic to both old and new systems simultaneously, compare results, only surface new system results when confidence is high
- **Seam**: The boundary point where interception is introduced — choosing the right seam is the critical first design decision

## In Practice
Strangler Fig is the default approach for brownfield modernization engagements at Method. It surfaces in Infrastructure Design as the migration topology decision. The key early question is always: where is the seam? API Gateway, load balancer, application router, or event stream — each has different tradeoffs. Pair with Circuit Breaker for resilience during the coexistence period.

## Engineering Knowledge
💡 **Engineering Knowledge — Strangler Fig**: Never rewrite a legacy system all at once. Build new functionality beside the old, intercept requests at a seam, and route incrementally. You deliver value throughout the migration, can halt or reverse at any point, and the legacy system is retired gradually rather than in a high-risk cutover. → `engineering-knowledge-repository/infrastructure/strangler-fig.md`

## Related Entries
- [Evolutionary Architecture](../architectural-philosophy/evolutionary-architecture.md) — Strangler Fig is the canonical EA migration pattern
- [Circuit Breaker](circuit-breaker.md) — resilience during the old/new coexistence period
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — event interception is a common Strangler Fig seam

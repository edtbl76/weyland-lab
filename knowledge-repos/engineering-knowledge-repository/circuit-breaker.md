---
id: circuit-breaker
tags: [pattern, reliability, distributed-systems, backend]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [event-driven-architecture, strangler-fig]
complexity: intermediate
---

# Circuit Breaker

## What It Is
A resilience pattern that prevents cascading failures in distributed systems. When calls to a downstream service start failing, the circuit breaker "opens" — subsequent calls fail immediately without hitting the downstream service, giving it time to recover. After a timeout, the breaker enters a "half-open" state and probes with a small number of requests. If they succeed, the circuit closes and normal traffic resumes. Named after the electrical circuit breaker.

## When to Apply
- Any service making synchronous calls to external services, databases, or downstream APIs
- Microservices architectures where one slow or failing service can cascade to others
- Systems with SLA requirements that cannot tolerate indefinite hangs from slow dependencies
- When you need graceful degradation — the ability to return a fallback response when a dependency is unavailable

## When Not to Apply
- In-process calls within a single service — Circuit Breaker is for network boundaries
- Fire-and-forget async calls where failures are handled by dead-letter queues
- Systems with no downstream dependencies

## Key Concepts
- **States**: Closed (normal), Open (failing fast), Half-Open (probing recovery)
- **Failure threshold**: How many failures trigger an Open state
- **Timeout**: How long the breaker stays Open before probing
- **Fallback**: What to return when the circuit is Open — cached data, default response, or explicit error
- **Libraries**: Resilience4j (Java), Polly (.NET), Hystrix (deprecated but widely referenced)

## In Practice
Circuit Breaker decisions surface in NFR Requirements (resilience expectations) and NFR Design (which calls need protection and what the fallback behavior is). In Infrastructure Design, it may be implemented at the service mesh level (Istio, AWS App Mesh) rather than in application code. Define your fallback behavior explicitly — "fail fast with a useful error" is a design decision, not an afterthought.

## Engineering Knowledge
💡 **Engineering Knowledge — Circuit Breaker**: Every synchronous call to an external dependency is a failure point. What happens to your service when that dependency is slow or down? A Circuit Breaker fails fast, protects your service from cascading failures, and gives downstream services time to recover. Define your fallback before you need it. → `engineering-knowledge-repository/infrastructure/circuit-breaker.md`

## Related Entries
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — async messaging reduces the need for circuit breakers by eliminating synchronous dependencies
- [Strangler Fig](strangler-fig.md) — Circuit Breaker is useful during brownfield modernization when the old and new systems coexist

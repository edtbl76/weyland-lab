---
id: api-gateway-pattern
tags: [pattern, api-design, backend, network, microservices]
surfaces-at: [application-design, infrastructure-design]
related: [microservices, backend-for-frontend, facade-pattern, circuit-breaker, strangler-fig]
complexity: intermediate
---

# API Gateway Pattern

## What It Is
An infrastructure pattern where a single entry point handles all client requests to a system, routing them to appropriate downstream services. The gateway handles cross-cutting concerns — authentication, rate limiting, request routing, protocol translation, response aggregation — so individual services don't have to. The API Gateway is a Facade at the infrastructure level.

## When to Apply
- Microservices systems where clients should not need to know about individual service addresses
- When cross-cutting concerns (auth, rate limiting, logging, SSL termination) should be centralized
- Multi-channel systems where different clients need different response shapes (see BFF)
- When implementing Strangler Fig — the gateway is the routing seam between old and new
- When external API versioning needs to be managed independently from internal service evolution

## When Not to Apply
- Simple single-service applications — an API gateway adds infrastructure complexity with no benefit
- When the gateway becomes a bottleneck or single point of failure that can't be addressed
- Avoid putting business logic in the gateway — it is infrastructure, not an application layer

## Key Concepts
- **Single Entry Point**: All external traffic enters through the gateway — services are not directly exposed
- **Cross-Cutting Concerns**: Auth, rate limiting, SSL termination, logging, tracing live at the gateway — services focus on business logic
- **Routing**: The gateway routes requests to appropriate services based on path, headers, or other criteria
- **Request Aggregation**: The gateway can aggregate multiple downstream calls into a single client response
- **Common Implementations**: AWS API Gateway, Kong, Nginx, Traefik, Azure API Management, AWS AppSync (GraphQL)

## In Practice
API Gateway is standard infrastructure in any microservices deployment. In Infrastructure Design, the gateway configuration is a first-class artifact. In Strangler Fig migrations, the gateway is typically the seam — routing requests to old or new implementations with feature flags or path-based rules. Don't put business logic in the gateway; keep it thin.

## Engineering Knowledge
💡 **Engineering Knowledge — API Gateway**: In a microservices system, clients shouldn't talk directly to services. An API Gateway provides a single entry point, handles auth and rate limiting centrally, and routes requests to the right service. It's also the natural seam for Strangler Fig migrations — route traffic to old or new implementations from one place. → `engineering-knowledge-repository/architectural-styles/api-gateway-pattern.md`

## Related Entries
- [Microservices](microservices.md) — API Gateway is standard infrastructure for microservices
- [Backend for Frontend](backend-for-frontend.md) — a specialized API Gateway per client type
- [Facade Pattern](../design-patterns/facade-pattern.md) — API Gateway is Facade at infrastructure scale
- [Strangler Fig](../infrastructure/strangler-fig.md) — the gateway is often the Strangler Fig routing seam

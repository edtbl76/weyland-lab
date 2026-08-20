---
id: backend-for-frontend
tags: [pattern, api-design, backend, frontend, microservices]
surfaces-at: [application-design, infrastructure-design]
related: [api-gateway-pattern, microservices, facade-pattern]
complexity: intermediate
---

# Backend for Frontend (BFF)

## What It Is
An architectural pattern where a dedicated backend service is created for each distinct frontend client type — web, mobile, third-party API, etc. Each BFF is optimized for the specific needs of its client, aggregating and transforming data from downstream services into exactly the shape the client needs. Coined by Sam Newman.

## When to Apply
- Systems with multiple client types (web app, mobile app, third-party integrations) that need different data shapes
- When a single general-purpose API is forced to serve too many different consumer needs, becoming a lowest-common-denominator
- When mobile clients need bandwidth-optimized responses that differ significantly from web responses
- When client-side teams want ownership over their API contract without depending on a shared backend team

## When Not to Apply
- Single client type — a general API Gateway is sufficient
- When the backends become a dumping ground for business logic — BFFs should aggregate and transform, not implement domain rules
- Small teams where maintaining multiple BFFs creates more overhead than benefit

## Key Concepts
- **Client-Specific API**: Each BFF exposes exactly what its client needs — no more, no less
- **Aggregation**: BFFs aggregate calls to multiple downstream services into a single client response
- **Transformation**: BFFs transform data into the shape the client requires — not the canonical domain shape
- **Team Ownership**: Frontend teams can own their BFF, giving them control over their API without depending on a shared backend team
- **Not Business Logic**: BFFs are aggregation and transformation layers — domain rules live in downstream services

## In Practice
BFF is common in Method engagements where clients have both web and mobile experiences with meaningfully different data requirements. The mobile BFF optimizes for bandwidth and battery; the web BFF can be richer. In Application Design, BFFs are identified when frontend requirements diverge significantly between client types. They sit between the API Gateway (routing) and the domain services (business logic).

## Engineering Knowledge
💡 **Engineering Knowledge — Backend for Frontend**: If your web app and mobile app are fighting over the same API shape, give each its own BFF. Each BFF aggregates downstream services into exactly what its client needs — optimized payloads, right fields, right granularity. Frontend teams own their BFF; domain logic stays downstream. → `engineering-knowledge-repository/architectural-styles/backend-for-frontend.md`

## Related Entries
- [API Gateway Pattern](api-gateway-pattern.md) — the entry point that routes to BFFs
- [Microservices](microservices.md) — BFFs are an aggregation layer over microservices

---
id: graphql-vs-rest
tags: [reference, api-design, backend]
surfaces-at: [application-design, requirements-analysis]
related: [graphql, rest-constraints, grpc, api-versioning, backend-for-frontend]
complexity: intermediate
---

# GraphQL vs. REST

## What It Is
A decision framework for choosing between GraphQL and REST as the API style for a given use case. Both are widely used; neither is universally superior. The choice depends on client diversity, data fetching patterns, team capabilities, and operational requirements. Choosing the wrong style creates friction that compounds over the lifetime of the API.

## When to Apply
- Designing a new public or internal API from scratch
- When an existing REST API has significant over-fetching/under-fetching pain
- When multiple clients (web, mobile, third-party) have divergent data needs

## Key Concepts

**Choose REST when**:
- Simple, resource-oriented CRUD operations with predictable data shapes
- Public API for third-party developers — REST is more universally understood, better tooling ecosystem (Postman, curl), easier to cache
- Team is unfamiliar with GraphQL — operational complexity is real
- HTTP caching is important — REST responses are cache-friendly; GraphQL POST requests are not
- Simple client needs — one client type with stable data requirements

**Choose GraphQL when**:
- Multiple clients (web, mobile, third-party) need different shapes of the same underlying data — eliminates over-fetching and under-fetching
- Rapid frontend iteration where data requirements change frequently without backend changes
- Complex, interconnected data graphs where clients need to traverse relationships flexibly
- BFF (Backend for Frontend) layer — GraphQL as an aggregation layer over multiple REST/gRPC services

**GraphQL Tradeoffs**:
- `+` Clients request exactly the fields they need — no over-fetching
- `+` Single endpoint — no API versioning problem for field additions
- `+` Strongly typed schema is self-documenting
- `−` HTTP caching doesn't work naturally (all queries go to POST /graphql)
- `−` N+1 query problem — requires DataLoader pattern to batch and cache database calls
- `−` Rate limiting and authorization are more complex per-field than per-endpoint
- `−` Higher operational complexity — schema management, resolver debugging, query depth/complexity limits

**REST Tradeoffs**:
- `+` Simple, cacheable, universally understood
- `+` HTTP semantics map naturally to CRUD operations
- `+` Per-endpoint rate limiting and authorization are straightforward
- `−` Over-fetching (endpoint returns more than client needs) and under-fetching (multiple requests needed) are common
- `−` API versioning is required for breaking changes

**gRPC**: Choose over both for internal service-to-service communication where performance and strict contracts matter — binary protocol, generated clients, streaming support. Not suitable for browser clients without a translation layer.

## In Practice
Method defaults to REST for public APIs and simple internal services. GraphQL is used when a BFF layer is needed to aggregate multiple services for a client with complex, evolving data requirements. gRPC is used for high-throughput internal service communication. The hybrid pattern — REST for external, GraphQL BFF for frontend, gRPC for internal — is common in Method's client architectures.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — GraphQL vs. REST**: Default to REST — it's simpler, cacheable, and universally understood. Reach for GraphQL when you have multiple clients with divergent data needs or a frontend that needs flexible data fetching without backend changes. If you use GraphQL, solve the N+1 problem with DataLoader from day one — it's a production reliability issue, not a nice-to-have. Don't use GraphQL for public third-party APIs — REST has better ecosystem support and is easier for external developers. gRPC belongs in internal service-to-service communication, not client-facing APIs. → `engineering-knowledge-repository/graphql-vs-rest.md`

## Related Entries
- [GraphQL](graphql.md) — GraphQL concepts, patterns, and implementation details
- [REST Constraints](rest-constraints.md) — REST architectural constraints and when they apply
- [gRPC](grpc.md) — gRPC for high-performance internal service communication
- [API Versioning](api-versioning.md) — REST requires versioning strategies that GraphQL partially avoids
- [Backend for Frontend](backend-for-frontend.md) — GraphQL is commonly used as the BFF layer

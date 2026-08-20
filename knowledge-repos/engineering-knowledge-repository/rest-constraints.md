---
id: rest-constraints
tags: [principle, api-design, backend, network, protocol]
surfaces-at: [application-design, functional-design]
related: [openapi-specification, api-versioning, api-first-design, graphql]
complexity: foundational
---

# REST Constraints

## What It Is
REST (Representational State Transfer) is an architectural style defined by Roy Fielding in his 2000 dissertation. It is defined by six constraints — not a specification or protocol. APIs that satisfy these constraints are "RESTful." Many self-described REST APIs are not actually RESTful — they are HTTP APIs that use JSON. Understanding the actual constraints helps design APIs that are scalable, cacheable, and evolvable.

## When to Apply
- Designing public or internal APIs for resource-oriented interactions
- When HTTP semantics (methods, status codes, caching) align with the problem domain
- Client-server systems where loose coupling and independent evolvability matter

## When Not to Apply
- Streaming or event-driven interactions — consider SSE, WebSockets, or gRPC
- High-frequency, low-latency RPC between services where protocol overhead matters — consider gRPC
- When the interaction model is action-oriented rather than resource-oriented — consider RPC or GraphQL mutations

## Key Concepts
- **Uniform Interface**: The defining constraint of REST. Resources are identified by URIs. Representations (JSON, XML) are separate from resource identities. Messages are self-descriptive. HATEOAS: responses include links to related actions
- **Statelessness**: Each request contains all information needed to process it. No session state on the server. State that must persist lives in the client or in a resource on the server
- **Client-Server Separation**: UI and data storage are separated — they evolve independently. Improves portability and scalability
- **Cacheability**: Responses must be labeled cacheable or non-cacheable. HTTP Cache-Control, ETag, and Last-Modified headers enable CDN and client caching
- **Layered System**: Client cannot tell if it's connected to the end server or an intermediary (CDN, API gateway, load balancer). Enables scalability and security at layers
- **Code on Demand (Optional)**: Servers can send executable code to clients (JavaScript). Rarely used in practice
- **HTTP Method Semantics**: GET (safe, idempotent, cacheable), POST (non-idempotent create), PUT (idempotent replace), PATCH (partial update), DELETE (idempotent remove)
- **HTTP Status Codes**: 200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity, 429 Too Many Requests, 500 Internal Server Error

## In Practice
Method REST APIs use noun-based resource URLs (`/orders/{id}`), appropriate HTTP verbs, and standard status codes. Idempotency is enforced for PUT and DELETE. POST endpoints return 201 Created with a Location header. Pagination uses cursor-based or offset patterns with `Link` headers. OpenAPI specification documents all endpoints.

## Engineering Knowledge
💡 **Engineering Knowledge — REST Constraints**: REST is defined by constraints, not by "uses JSON over HTTP." The critical ones: Statelessness (no server-side session), Uniform Interface (resources with URIs, representations, HATEOAS), Cacheability (HTTP cache headers). Use HTTP verbs correctly: GET is safe and idempotent; PUT is idempotent replace; PATCH is partial update. Return correct status codes — 201 (Created), 204 (No Content), 422 (Validation Error), 429 (Rate Limited). Most "REST" APIs are HTTP/JSON APIs — that's fine, but know what you're trading away. → `engineering-knowledge-repository/api-design/rest-constraints.md`

## Related Entries
- [OpenAPI Specification](openapi-specification.md) — the standard for documenting REST APIs
- [API Versioning](api-versioning.md) — evolving REST APIs without breaking clients
- [API First Design](api-first-design.md) — design API contracts before implementation
- [GraphQL](graphql.md) — an alternative to REST for flexible data querying

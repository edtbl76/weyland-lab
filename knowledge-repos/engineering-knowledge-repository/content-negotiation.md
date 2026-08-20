---
id: content-negotiation
tags: [pattern, api-design, backend, network, protocol]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, api-versioning, openapi-specification, graphql, hateoas]
complexity: foundational
---

# Content Negotiation

## What It Is
The HTTP mechanism by which a client and server agree on the format of the response. The client advertises what it can accept; the server responds with the best match it can provide. Content negotiation enables a single endpoint to serve multiple representations of the same resource — JSON, XML, CSV, different API versions — without requiring separate URLs. It is one of the underused features of HTTP that, when applied well, produces cleaner and more evolvable APIs.

## When to Apply
- APIs that need to serve multiple response formats (JSON and XML, or JSON and CSV exports)
- API versioning via media types — an alternative to URL versioning
- APIs implementing HATEOAS with typed media types

## When Not to Apply
- APIs with a single response format — content negotiation adds complexity with no benefit
- When URL-based format selection (`?format=csv`) is simpler and sufficient for the use case

## Key Concepts
- **`Accept` Header**: The client specifies acceptable response media types in preference order:
  `Accept: application/json;q=1.0, application/xml;q=0.8, */*;q=0.5`
  - `q` values indicate preference (1.0 = most preferred, default if omitted)
- **`Content-Type` Header**: On requests with a body, specifies the format of the payload being sent. On responses, specifies the format of the response body
- **`406 Not Acceptable`**: Returned when the server cannot produce any of the formats the client accepts
- **`415 Unsupported Media Type`**: Returned when the server cannot process the `Content-Type` of the request body
- **`Vary: Accept`**: The response must include this header when content negotiation is in use — tells caches that the response varies by the `Accept` header, preventing the wrong representation from being cached and served to another client
- **Versioning via Media Types**: An alternative to URL versioning — `Accept: application/vnd.api.v2+json`. Keeps URLs clean and version-agnostic. More complex for clients to implement than URL versioning
- **Proactive vs. Reactive Negotiation**: Proactive (server chooses based on `Accept`). Reactive (server returns `300 Multiple Choices` with options; client picks). Proactive is almost universal in practice
- **Format Parameters**: Media types can carry parameters — `application/json; charset=utf-8` or `application/vnd.api+json; version=2`

## In Practice
Method APIs default to `application/json`. Content negotiation is added when a second format is required (e.g., CSV export for reporting endpoints). `Vary: Accept` is included whenever negotiation is active. API versioning via media types is supported as an option for consumers who prefer it, alongside URL versioning. `406` and `415` responses follow the RFC 7807 error format.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Content Negotiation**: The `Accept` header lets clients declare what they want; the server delivers the best match or returns `406`. Use it when an endpoint needs to serve multiple formats (JSON + CSV, or versioned representations). Always include `Vary: Accept` in responses — without it, CDNs and proxies will serve the wrong format to the wrong client. For versioning via media type (`application/vnd.api.v2+json`), it keeps URLs clean but increases client implementation complexity. `Content-Type` on the request body and `415` on unsupported types are the request-side counterparts. → `engineering-knowledge-repository/content-negotiation.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — content negotiation is part of REST's uniform interface constraint
- [API Versioning](api-versioning.md) — media type versioning is an alternative to URL versioning
- [OpenAPI Specification](openapi-specification.md) — OpenAPI documents supported media types per operation
- [GraphQL](graphql.md) — GraphQL sidesteps content negotiation by using a single typed schema
- [HATEOAS](hateoas.md) — HATEOAS uses typed media types to describe hypermedia representations

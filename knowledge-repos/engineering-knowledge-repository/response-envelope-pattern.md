---
id: response-envelope-pattern
tags: [pattern, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, pagination-patterns, error-response-standards, api-first-design]
complexity: foundational
---

# Response Envelope Pattern

## What It Is
A design decision about whether API responses wrap their payload in a consistent outer structure (an "envelope") or return the resource directly (bare response). An envelope looks like `{ "data": {...}, "meta": {...} }`. A bare response returns the resource directly: `{ "id": "123", "name": "..." }`. Both are valid — the critical principle is consistency: choose one and apply it across all endpoints.

## When to Apply
- Decide at API design time, before the first endpoint is built
- Apply consistently to all endpoints — inconsistency is the failure mode, not the choice itself

## Key Concepts
- **Bare Response**: The resource is returned directly as the response body. Cleaner, more RESTful, idiomatic for single-resource endpoints. `GET /users/123` → `{ "id": "123", "name": "Alice" }`. HTTP headers carry metadata (pagination `Link` headers, `ETag`, `Last-Modified`)
- **Envelope Response**: The resource is nested inside a `data` key. Metadata (pagination, request ID, warnings) lives alongside in the envelope:
  ```json
  {
    "data": { "id": "123", "name": "Alice" },
    "meta": { "request_id": "req_abc", "version": "1.0" }
  }
  ```
- **Collection Envelopes**: Envelopes are most natural for collections where pagination metadata accompanies the array:
  ```json
  {
    "data": [ {...}, {...} ],
    "meta": { "total": 142, "next_cursor": "abc123" }
  }
  ```
- **JSON:API**: A formal specification for envelope-based JSON APIs — defines `data`, `included`, `errors`, `meta`, `links` structure. High consistency; significant boilerplate
- **Envelope Pitfalls**: Nested `data.data` when an API returns a resource that itself has a `data` field. Inconsistency where some endpoints use envelopes and others don't — the worst outcome
- **HTTP Headers as Metadata**: The REST-native alternative to envelopes for metadata: `Link` headers for pagination, `ETag` for caching, `X-Request-ID` for correlation. Keeps the body clean; requires clients to read headers
- **The Hybrid Mistake**: Bare responses for single resources + envelopes for collections is a common inconsistency. If using envelopes, use them everywhere. If using bare responses, use HTTP headers for metadata everywhere

## In Practice
Method APIs use a consistent envelope for collection endpoints (pagination metadata in `meta`) and bare responses for single-resource endpoints with HTTP headers for metadata. The pattern is documented in the API style guide and enforced in OpenAPI schema definitions and code review.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Response Envelope Pattern**: Pick one approach and apply it everywhere — inconsistency is the failure mode. Bare responses are cleaner and more idiomatic for single resources; use HTTP headers (`Link`, `ETag`) for metadata. Envelopes are practical for collections where pagination metadata naturally accompanies the array. Never use envelopes inconsistently — bare for some endpoints, enveloped for others — it forces clients to handle multiple shapes. Document the choice in your API style guide and enforce it in OpenAPI schemas. → `engineering-knowledge-repository/api-design/response-envelope-pattern.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — REST-native metadata lives in HTTP headers, not response bodies
- [Pagination Patterns](pagination-patterns.md) — pagination metadata is the primary driver for collection envelopes
- [Error Response Standards](error-response-standards.md) — errors use RFC 7807, not the same envelope as success responses
- [API First Design](api-first-design.md) — response shape decisions belong in the design phase

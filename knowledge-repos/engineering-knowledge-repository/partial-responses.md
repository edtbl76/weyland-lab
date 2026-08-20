---
id: partial-responses
tags: [pattern, api-design, backend, network]
surfaces-at: [application-design, functional-design, nfr-requirements]
related: [rest-constraints, graphql, openapi-specification, response-envelope-pattern, pagination-patterns, filtering-and-sorting]
complexity: intermediate
---

# Partial Responses (Sparse Fieldsets)

## What It Is
A mechanism that allows API clients to request only the specific fields they need rather than the full resource representation. Instead of always returning a 50-field user object when a mobile client only needs `id`, `name`, and `avatar_url`, the client specifies `?fields=id,name,avatar_url` and receives a smaller payload. Reduces bandwidth, improves latency, and removes the need for the server to serialize unused data. Used by Google APIs, GitHub, Stripe, and Facebook's Graph API.

## When to Apply
- APIs consumed by mobile clients where bandwidth and battery are constrained
- Resources with many fields where different consumers consistently need different subsets
- High-traffic endpoints where payload size reduction has meaningful infrastructure cost impact
- As a mitigation for over-fetching in REST APIs (addressing one of GraphQL's core selling points)

## When Not to Apply
- Simple APIs with small, stable resource representations — the added complexity isn't worth it
- Resources where all fields are always needed by all clients
- When adopting GraphQL — field selection is built into GraphQL's query model; partial responses are the REST workaround for the same problem

## Key Concepts
- **`?fields=` Query Parameter**: The most common convention — comma-separated list of field names: `GET /users/123?fields=id,name,email,avatar_url`
- **Nested Field Selection**: Dot notation for nested objects: `?fields=id,name,address.city,address.country`
- **Google's Partial Response**: `?fields=items(id,name),nextPageToken` — supports nested selection and array item projection. The most fully-featured REST field selection syntax
- **JSON:API Sparse Fieldsets**: `?fields[users]=name,email&fields[posts]=title` — per-type field selection when responses include related resources
- **Response Shape**: The response structure stays the same — absent fields are simply omitted, not replaced with null. Clients must handle missing fields gracefully
- **Caching Implications**: Different `?fields=` values produce different response shapes — CDN and server-side caches must use the full URL (including query string) as the cache key. `Vary` headers don't help here since it's a query parameter. Consider whether field selection is worth the cache fragmentation
- **OpenAPI Documentation**: Document that `?fields=` is supported and enumerate the available fields. Since the response schema changes based on the parameter, use `anyOf` or document it descriptively
- **vs. GraphQL**: Partial responses are the REST approximation of GraphQL's field selection. GraphQL does it more elegantly (typed, validated, introspectable) but requires schema infrastructure. Partial responses are simpler to add to an existing REST API

## In Practice
Method adds `?fields=` support to REST endpoints where mobile clients or high-traffic consumers have identified specific over-fetching problems. It is not added by default to every endpoint. When added, all valid field names are documented in OpenAPI. Nested selection uses dot notation. Cache keys include the full query string.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Partial Responses**: Add `?fields=id,name,email` support when clients are consistently fetching more than they use — particularly on mobile. It's the REST answer to GraphQL's field selection. Use dot notation for nested fields. Omit absent fields from the response entirely (don't null them). Watch cache fragmentation — each unique `?fields=` value is a different cache entry. Don't add it everywhere by default; add it where over-fetching is a measured problem. If you're building from scratch and field selection is a core requirement, consider whether GraphQL is the better fit. → `engineering-knowledge-repository/partial-responses.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — partial responses are a REST extension for representation efficiency
- [GraphQL](graphql.md) — GraphQL's field selection is the schema-native alternative to partial responses
- [OpenAPI Specification](openapi-specification.md) — partial response fields must be documented as query parameters
- [Response Envelope Pattern](response-envelope-pattern.md) — partial responses affect the resource payload, not the envelope structure
- [Filtering and Sorting](filtering-and-sorting.md) — filtering narrows the collection; partial responses narrow each resource's fields

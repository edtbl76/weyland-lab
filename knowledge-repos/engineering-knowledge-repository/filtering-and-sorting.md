---
id: filtering-and-sorting
tags: [pattern, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, pagination-patterns, openapi-specification, query-optimization]
complexity: foundational
---

# Filtering and Sorting

## What It Is
The conventions for allowing API clients to narrow and order collection results via query parameters. Every non-trivial collection endpoint needs filtering and sorting — without them, clients receive everything and filter client-side, which is wasteful and doesn't scale. Unlike pagination (which is widely standardized), filtering and sorting have no single dominant convention — but within a single API, consistency is mandatory.

## When to Apply
- Any collection endpoint where clients need to query a subset of results
- Establish the convention at API design time and apply it uniformly — inconsistency across endpoints forces clients to handle multiple query styles

## Key Concepts

**Filtering Approaches**:

- **Simple key-value**: `?status=active&type=premium` — simplest, works for equality filters, no support for operators
- **Bracket notation**: `?filter[status]=active&filter[created_at][gte]=2024-01-01` — supports operators, explicit namespace. Used by JSON:API
- **LHS colon**: `?status:eq=active&price:gte=100` — compact, operator in the key. Used by some REST frameworks
- **Query DSL parameter**: `?q=status:active AND price>100` — flexible but complex to parse and document
- **Method recommendation**: Bracket notation or simple key-value for most APIs. Reserve query DSL for search-specific endpoints

**Operators**:
Common filter operators to support: `eq` (equals, default), `ne` (not equal), `gt`/`gte` (greater than), `lt`/`lte` (less than), `in` (member of set: `?filter[status][in]=active,pending`), `like` (pattern match)

**Sorting**:
- **`?sort=field`** for ascending, **`?sort=-field`** for descending (minus prefix convention — widely adopted)
- Multiple sort fields: `?sort=-created_at,name` — comma-separated, applied in order
- Always document the default sort order — undocumented defaults cause non-deterministic pagination

**Search**:
- `?search=keyword` or `?q=keyword` for full-text search across relevant fields
- Keep search separate from filter — they are different operations (structured vs. full-text)

**Validation**:
- Reject unknown filter fields with `400 Bad Request` — silent ignoring leads to clients thinking they're filtering when they're not
- Validate operator applicability — `?filter[name][gte]=foo` on a string field should return `400`

**Documentation**:
- Every filterable field, sortable field, and supported operator must be documented in OpenAPI — use `description` to enumerate options since OpenAPI doesn't have a native filter syntax

## In Practice
Method APIs use bracket notation for filtering (`?filter[status]=active`) and minus-prefix for sorting (`?sort=-created_at`). All filterable and sortable fields are enumerated in OpenAPI. Unknown filter parameters return `400`. Default sort order is always documented. Full-text search uses `?search=` as a separate parameter.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Filtering and Sorting**: Agree on a convention before building the first endpoint — inconsistency is the failure mode. Bracket notation (`?filter[status]=active`) is explicit and extensible. Minus-prefix sorting (`?sort=-created_at,name`) is widely understood. Always document the default sort order — undocumented defaults cause non-deterministic cursor pagination. Reject unknown filter fields with `400` rather than silently ignoring them. Keep full-text search (`?search=`) separate from structured filters. → `engineering-knowledge-repository/filtering-and-sorting.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — filtering is applied to REST collection resources via query parameters
- [Pagination Patterns](pagination-patterns.md) — filtering and sorting interact with pagination; sort order determines cursor stability
- [OpenAPI Specification](openapi-specification.md) — filterable and sortable fields must be documented as query parameters
- [Query Optimization](query-optimization.md) — filter parameters translate to WHERE clauses; indexes must support common filter combinations

---
id: restful-resource-design
tags: [pattern, api-design, backend]
surfaces-at: [functional-design, application-design]
related: [rest-constraints, hateoas, api-versioning, openapi-specification, filtering-and-sorting, pagination-patterns, error-response-standards]
complexity: beginner
---

# RESTful Resource Design

## What It Is
The practical conventions for structuring URLs, naming resources, and mapping HTTP methods to operations in a REST API. REST constraints (statelessness, uniform interface, etc.) define the architectural principles; resource design defines the day-to-day decisions: what URLs look like, how resources are named, when to nest vs. flatten, and how operations map to HTTP verbs. Inconsistent resource design produces APIs that are confusing to consume, hard to version, and difficult to document.

## When to Apply
- Designing any new REST API endpoint or resource
- Reviewing API designs for consistency before implementation
- Onboarding engineers to an existing API's conventions

## Key Concepts
- **Nouns, Not Verbs**: URLs identify resources, not actions. `/orders` not `/getOrders`; `/users/{id}/activate` is an anti-pattern — use `/users/{id}/status` (PATCH) or a sub-resource like `/users/{id}/activation` (POST)
- **Plural Nouns for Collections**: `/users`, `/orders`, `/products` — plural for collection endpoints. `/users/{id}` for a single resource
- **HTTP Methods Map to Operations**:
  - `GET` — read, safe, idempotent
  - `POST` — create (collection) or trigger action
  - `PUT` — full replace, idempotent
  - `PATCH` — partial update
  - `DELETE` — remove, idempotent
- **Nesting vs. Flattening**: Nest when the sub-resource only exists in the context of the parent (`/orders/{id}/items`). Flatten when the sub-resource has independent existence or is queried across parents (`/items?orderId=` rather than deeply nested `/users/{id}/orders/{id}/items`). Limit nesting to two levels deep
- **Resource Hierarchy Reflects Ownership**: `/users/{id}/addresses` is correct if addresses belong to a user. `/addresses/{id}` is correct if addresses are independently addressable. Don't nest for the sake of showing relationships — use links or query parameters instead
- **Singleton Resources**: Some resources are singular — there's only one per parent. `/users/{id}/profile`, `/accounts/{id}/settings`. Use singular nouns for singletons
- **Actions That Don't Map to CRUD**: Use POST to a sub-resource noun. `/payments/{id}/refund` → `/payments/{id}/refunds` (POST). `/users/{id}/password-reset` → POST creates a password reset. Avoid verbs in URLs; find the noun
- **Consistent ID Strategy**: Use UUIDs or opaque IDs in URLs — never expose sequential database IDs. Consistent across all resources
- **Query Parameters for Filtering, Sorting, Pagination**: Resource state goes in the path; query modifiers go in query params. `/orders?status=shipped&sort=created_at&page=2`
- **Response Codes**:
  - `200 OK` — successful GET, PATCH, PUT
  - `201 Created` — successful POST that creates a resource; include `Location` header
  - `204 No Content` — successful DELETE or action with no response body
  - `400/422` — client error; `404` — not found; `409` — conflict

## In Practice
Method REST APIs use plural nouns, two-level max nesting, UUID resource IDs, and consistent HTTP method semantics. All resources are documented in OpenAPI before implementation. Actions that don't fit CRUD are modeled as sub-resource nouns with POST. Query parameters handle all filtering, sorting, and pagination.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — RESTful Resource Design**: Use nouns not verbs — URLs name things, HTTP methods name actions. Plural collections (`/users`), singleton sub-resources for one-per-parent (`/users/{id}/profile`). Nest at most two levels deep; flatten anything deeper into query parameters. When an action doesn't fit CRUD, find the noun — `POST /payments/{id}/refunds` instead of `POST /payments/{id}/refund`. Use 201 + Location header on successful creates; 204 on successful deletes. Consistency matters more than perfection — a coherent convention throughout an API beats locally optimal but inconsistent choices. → `engineering-knowledge-repository/restful-resource-design.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — the architectural constraints that RESTful resource design implements
- [HATEOAS](hateoas.md) — hypermedia links connect related resources in REST responses
- [API Versioning](api-versioning.md) — resource design decisions affect how versioning is applied
- [OpenAPI Specification](openapi-specification.md) — resource design is documented and enforced through OpenAPI schemas
- [Filtering and Sorting](filtering-and-sorting.md) — query parameter conventions for filtering and sorting collection resources
- [Pagination Patterns](pagination-patterns.md) — pagination conventions for collection resources
- [Error Response Standards](error-response-standards.md) — consistent error responses across all resource endpoints

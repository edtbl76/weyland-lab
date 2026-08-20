---
id: api-versioning
tags: [methodology, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, openapi-specification, api-deprecation, api-first-design]
complexity: intermediate
---

# API Versioning

## What It Is
The strategy for evolving an API over time without breaking existing clients. Every non-trivial API will need to change — adding fields, renaming operations, removing deprecated functionality. Versioning provides a contract: existing clients are not broken by changes within their version; breaking changes are introduced only in new versions with an explicit migration path.

## When to Apply
- Any API with external consumers (public APIs, client-facing APIs, partner integrations)
- Internal APIs where multiple teams consume the API and cannot be updated simultaneously
- Before the first public release — decide on a versioning strategy upfront

## Key Concepts
- **URI Versioning**: Version in the URL path — `/api/v1/users`, `/api/v2/users`. Explicit, easy to route, easy to debug. Most common approach
- **Header Versioning**: Version in a request header — `Accept: application/vnd.api.v2+json` or `API-Version: 2`. Cleaner URLs but harder to test in a browser
- **Query Parameter Versioning**: `?version=2`. Simple but pollutes query parameters; not widely recommended
- **Semantic Versioning for APIs**: MAJOR (breaking changes), MINOR (backward-compatible additions), PATCH (bug fixes). Public API contracts expose MAJOR version; MINOR/PATCH are transparent
- **Breaking Change**: A change that breaks existing clients — removing a field, changing a field type, removing an endpoint, changing authentication requirements
- **Non-Breaking Change**: Adding new optional fields, adding new endpoints, adding new enum values (with caveats) — these can deploy without a version bump
- **Tolerance by Clients**: Clients should be designed to be tolerant — ignore unknown fields (Postel's Law), don't fail on new enum values. Reduces how often breaking changes are truly breaking
- **Versioning Granularity**: Whole-API versioning (simplest), resource-level versioning (more granular), operation-level versioning (most granular, most complex)

## In Practice
Method uses URI versioning (`/v1/`, `/v2/`) for all public and partner-facing APIs. Internal microservice APIs version via header to avoid URL coupling. Non-breaking changes are deployed without version changes. Breaking changes go through a deprecation cycle: announce, provide migration guide, support old version for a defined period (minimum 6 months for external consumers), then remove.

## Engineering Knowledge
💡 **Engineering Knowledge — API Versioning**: Decide on a versioning strategy before the first consumer. URI versioning (`/v1/`) is simplest and most explicit. Only introduce a new version for breaking changes — removing fields, changing types, removing endpoints. Additions are non-breaking (if clients are tolerant per Postel's Law). Support old versions for 6+ months after deprecation notice. Never remove a version without an announced sunset date. Build tolerant clients — ignore unknown fields — to minimize version churn. → `engineering-knowledge-repository/api-design/api-versioning.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — REST APIs are the primary target of URL versioning patterns
- [OpenAPI Specification](openapi-specification.md) — OpenAPI documents the contract for each version
- [API Deprecation](api-deprecation.md) — deprecation is the process for retiring old API versions
- [API First Design](api-first-design.md) — versioning decisions should be made in the design phase

---
id: api-deprecation
tags: [methodology, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [api-versioning, openapi-specification, api-first-design]
complexity: intermediate
---

# API Deprecation

## What It Is
The process of retiring an API version, endpoint, or operation in a controlled, communicated way that gives consumers time to migrate. Deprecation is not deletion — it is a signal that something will be removed on a future date, accompanied by a migration path. Poorly managed deprecation breaks consumer systems without warning; well-managed deprecation gives consumers months to migrate with no surprises.

## When to Apply
- When introducing a v2 that supersedes a v1 — v1 enters deprecation
- When removing or changing an endpoint in a way that breaks backward compatibility
- When retiring a feature that was available via API

## Key Concepts
- **Deprecation vs. Sunset**: Deprecation announces intent to remove; sunset is the actual removal date. Both should be communicated explicitly
- **Sunset HTTP Header**: `Sunset: Sat, 31 Dec 2025 23:59:59 GMT` — machine-readable removal date. RFC 8594
- **Deprecation HTTP Header**: `Deprecation: true` or `Deprecation: <date>` — signals the response is from a deprecated operation
- **OpenAPI `deprecated: true`**: Mark operations in the spec as deprecated — tooling surfaces this to API consumers
- **Migration Guide**: Documentation explaining what replaces the deprecated API and step-by-step migration instructions — required before announcing deprecation
- **Deprecation Timeline**: Minimum 6 months for external consumers; 3 months for internal. Announce → provide migration guide → enforce sunset → remove
- **Usage Analytics**: Track deprecated endpoint usage to identify consumers who haven't migrated — proactively notify them before the sunset date

## In Practice
Method announces API deprecation via changelog, email (for registered API consumers), and HTTP response headers. The `Sunset` header is added to all deprecated endpoint responses. Swagger UI marks deprecated operations visually. Sunset dates are enforced — traffic to removed endpoints returns 410 Gone with a link to the migration guide.

## Engineering Knowledge
💡 **Engineering Knowledge — API Deprecation**: Deprecation is a promise with a deadline — announce early, give a migration guide, then enforce. Add `Sunset` and `Deprecation` HTTP headers so tooling can surface the timeline automatically. Mark operations `deprecated: true` in OpenAPI. Give external consumers minimum 6 months from announcement to sunset. Track who's still calling deprecated endpoints and notify them proactively. Return 410 Gone after removal — not 404. → `engineering-knowledge-repository/api-design/api-deprecation.md`

## Related Entries
- [API Versioning](api-versioning.md) — deprecation is the mechanism for retiring old API versions
- [OpenAPI Specification](openapi-specification.md) — OpenAPI `deprecated: true` marks operations for deprecation
- [API First Design](api-first-design.md) — deprecation strategy should be defined during API design

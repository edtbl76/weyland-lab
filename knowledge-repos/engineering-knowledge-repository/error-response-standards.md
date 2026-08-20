---
id: error-response-standards
tags: [reference, api-design, backend]
surfaces-at: [application-design, functional-design, code-generation]
related: [rest-constraints, openapi-specification, api-first-design]
complexity: foundational
---

# Error Response Standards

## What It Is
A consistent, machine-readable format for API error responses across all endpoints. Without a standard, every endpoint returns errors differently — some return `{ "error": "..." }`, others `{ "message": "..." }`, others a plain string. This forces clients to handle every possible error shape. RFC 7807 (Problem Details for HTTP APIs) defines the standard: a structured JSON error body that is consistent, extensible, and self-describing.

## When to Apply
- All API endpoints — error format consistency is a baseline API quality requirement
- Establish the standard before the first endpoint is built; retrofitting is expensive

## Key Concepts
- **RFC 7807 Problem Details**: The standard format — `Content-Type: application/problem+json`:
  ```json
  {
    "type": "https://api.example.com/errors/insufficient-funds",
    "title": "Insufficient Funds",
    "status": 400,
    "detail": "Account balance $10.00 is below the required $50.00",
    "instance": "/orders/abc123"
  }
  ```
- **`type`**: A URI identifying the error type — stable, machine-readable, linkable to documentation. Not a human message
- **`title`**: A short, human-readable summary of the error type. Consistent for the same `type` — does not change per request
- **`detail`**: A human-readable explanation specific to this occurrence — can include request-specific context
- **`instance`**: A URI identifying the specific occurrence — useful for support and correlation
- **Extensions**: RFC 7807 is extensible — add `errors` array for validation errors, `trace_id` for observability correlation, `code` for application-specific error codes
- **Validation Errors**: Return `422 Unprocessable Entity` with an `errors` array listing field-level violations: `{ "field": "email", "message": "must be a valid email" }`
- **Never Expose Internals**: Stack traces, SQL errors, file paths, and internal service names must never appear in error responses — security and usability concern
- **HTTP Status Code Discipline**: Use codes correctly and consistently. 400 (bad input), 401 (not authenticated), 403 (not authorized), 404 (not found), 409 (conflict), 422 (validation), 429 (rate limited), 500 (server error). Do not return 200 with an error body

## In Practice
Method APIs implement RFC 7807 as the standard error format. Error `type` URIs are documented in OpenAPI. Validation errors include a field-level `errors` array extension. `trace_id` is always included for observability correlation. A shared error middleware handles formatting — individual endpoints throw typed exceptions, middleware serializes them.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Error Response Standards**: Consistent error shapes are a first-class API quality concern. Adopt RFC 7807 — `type` (machine-readable URI), `title` (stable summary), `detail` (request-specific explanation), `status` (HTTP code). Extend with `trace_id` for observability and `errors[]` for field-level validation failures. Never return stack traces. Never return 200 with an error body. Use correct HTTP status codes — 422 for validation, 429 for rate limiting, 409 for conflicts. Document error types in OpenAPI. → `engineering-knowledge-repository/api-design/error-response-standards.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — HTTP status code semantics
- [OpenAPI Specification](openapi-specification.md) — error responses are documented as OpenAPI response schemas
- [API First Design](api-first-design.md) — error format is decided during API design, not implementation

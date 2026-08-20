---
id: request-validation
tags: [pattern, api-design, security, backend]
surfaces-at: [functional-design, code-generation]
related: [error-response-standards, openapi-specification, api-security, input-validation]
complexity: beginner
---

# Request Validation

## What It Is
The systematic validation of incoming API requests at the API boundary before any business logic executes. Request validation enforces that required fields are present, types are correct, values are within acceptable ranges, and strings conform to expected formats. It is a security and correctness requirement — unvalidated input is the root cause of injection attacks, unexpected behavior, and hard-to-debug failures deep in the call stack. Fail fast at the boundary: return a clear 400/422 before bad data reaches your database or downstream services.

## When to Apply
- Every API endpoint that accepts input — no exceptions
- At the API layer, not just in business logic — defense in depth, but the boundary is the primary gate
- Before any database query, external service call, or state mutation

## Key Concepts
- **400 Bad Request vs. 422 Unprocessable Entity**:
  - `400`: Malformed request — cannot be parsed (invalid JSON, missing Content-Type)
  - `422`: Well-formed request with invalid semantics — valid JSON but fails validation rules (missing required field, invalid enum value, value out of range)
  - Use 422 for validation failures — it's more precise and clients can distinguish parse errors from semantic errors
- **Schema Validation**: Validate the entire request against a defined schema before handler execution. JSON Schema, Pydantic (Python), Zod (TypeScript/JS), Joi — framework-integrated schema validators that produce structured error responses automatically
- **Validation Error Response**: Return all validation errors in a single response — not just the first one found. Clients need the full list to fix the request in one round trip. Use RFC 7807 Problem Details format or a consistent errors array
- **Required vs. Optional Fields**: Explicitly declare which fields are required. Missing required fields → 422 with the field name and "required" message
- **Type Coercion**: Decide explicitly whether to coerce types (string "123" → integer 123) or reject type mismatches. Strict APIs reject; lenient APIs coerce. Be consistent and document the behavior
- **String Validation**: Length limits (prevent excessively large payloads), format validation (email, UUID, date formats), pattern matching (regex for structured strings like phone numbers). Validate before storing
- **Numeric Bounds**: Min/max values for numeric fields. Reject negative quantities, future dates for past-event fields, values outside business-meaningful ranges
- **Allowlist vs. Blocklist**: For string fields, allowlist acceptable values (enum validation) rather than blocklisting known-bad values. Blocklists always miss cases
- **Validation at the Framework Layer**: Use middleware or framework hooks to run validation before the handler — keeps handler code clean and ensures validation cannot be bypassed by forgetting to call it

## In Practice
Method APIs use Pydantic for Python services (automatic validation from type annotations) and Zod for TypeScript services. Validation runs as middleware before any handler executes. All 422 responses return the full list of validation errors in a structured `errors` array. OpenAPI schemas are generated from Pydantic/Zod models — the schema definition is the source of truth for both validation and documentation.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Request Validation**: Validate at the boundary, before business logic — never assume callers send well-formed input. Return 422 (not 400) for semantic validation failures and include all errors in one response. Use a schema validation library (Pydantic, Zod) integrated with your framework so validation is declarative and enforced automatically — don't write ad hoc validation in every handler. Generate your OpenAPI schema from your validation models so documentation and validation stay in sync. Allowlist acceptable values; never try to blocklist bad input. → `engineering-knowledge-repository/request-validation.md`

## Related Entries
- [Error Response Standards](error-response-standards.md) — validation errors must follow the API's standard error response format
- [OpenAPI Specification](openapi-specification.md) — request schemas defined in OpenAPI drive validation rules
- [API Security](api-security.md) — input validation is the first line of defense against injection and malformed input attacks
- [Input Validation](input-validation.md) — general input validation principles that apply beyond APIs

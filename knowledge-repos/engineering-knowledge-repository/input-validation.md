---
id: input-validation
tags: [principle, security, backend]
surfaces-at: [functional-design, code-generation]
related: [request-validation, api-security, injection-attacks, defense-in-depth]
complexity: beginner
---

# Input Validation

## What It Is
The practice of verifying that all data entering a system meets expected format, type, range, and business rule constraints before processing it. Input validation is a foundational security and correctness control — unvalidated input is the root cause of injection attacks (SQL, command, XSS), unexpected application behavior, and data corruption. The principle: never trust data from outside your trust boundary. Validate early, validate completely, reject anything that doesn't conform.

## When to Apply
- Every system boundary where external data enters: API requests, form submissions, file uploads, message queue messages, webhook payloads, CLI arguments
- Before any database write, external service call, or business logic execution
- Defense in depth — validate at the boundary AND within service layers for high-risk operations

## Key Concepts
- **Trust Boundaries**: Data from outside your system (users, external APIs, third-party services, other microservices) is untrusted. Data generated internally is trusted. Validate at every trust boundary crossing
- **Allowlisting over Blocklisting**: Define what is acceptable and reject everything else. Never try to enumerate what is bad — attackers always find new patterns. Accept only known-good formats, values, and characters
- **Validate All Attributes**: Type, length, format, range, and business rules. A string validated for length but not format can still carry injection payloads
- **Fail Fast and Completely**: Reject invalid input immediately at the boundary. Return all validation errors at once (not just the first). Do not attempt to sanitize and continue — reject and require the caller to fix
- **Sanitization vs. Validation**: Validation rejects bad input. Sanitization transforms potentially bad input into safe form (HTML encoding for XSS, parameterized queries for SQL). Both are needed — sanitization is not a substitute for validation
- **File Upload Validation**: Validate file type by magic bytes (not extension), enforce size limits, scan for malware, store outside the web root, generate random filenames
- **Business Rule Validation**: Beyond format — validate that values make business sense (end date after start date, quantity > 0, referenced entity exists). Business rule violations are 422 errors
- **Client-Side Validation is UX, Not Security**: Client-side validation improves UX by catching errors early. It is not a security control — it is trivially bypassed. Server-side validation is always required

## In Practice
Method APIs use Pydantic (Python) and Zod (TypeScript) for schema-level validation at API boundaries. Business rule validation runs in the service layer. File uploads are validated by content type and scanned before storage. All validation failures return 422 with a structured error list.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Input Validation**: Validate at every trust boundary — user input, external API responses, message queue payloads. Allowlist acceptable input; never blocklist. Validate type, length, format, range, AND business rules — partial validation leaves attack surface. Client-side validation is UX only — always validate server-side. Reject invalid input immediately; never sanitize-and-continue as a substitute for validation. File uploads require content-type validation by magic bytes, size limits, and out-of-web-root storage. → `engineering-knowledge-repository/input-validation.md`

## Related Entries
- [Request Validation](request-validation.md) — input validation applied specifically at API request boundaries
- [API Security](api-security.md) — input validation is a core API security control
- [Injection Attacks](injection-attacks.md) — unvalidated input is the root cause of all injection attack classes
- [Defense in Depth](defense-in-depth.md) — input validation is one layer in a defense-in-depth security strategy

---
id: api-security
tags: [reference, security, api-design, backend, network]
surfaces-at: [nfr-requirements, functional-design, application-design]
related: [oauth2-oidc, rbac, owasp-top-ten, zero-trust-security, principle-of-least-privilege]
complexity: intermediate
---

# API Security

## What It Is
The set of practices and controls for protecting APIs from unauthorized access, abuse, and data exposure. APIs are the primary attack surface for most modern applications — they expose business logic and data directly. API security covers: authentication, authorization, input validation, rate limiting, transport security, and data minimization.

## When to Apply
- All APIs — internal and external. Internal APIs are not automatically trusted.
- Before exposing any API endpoint to clients
- API design reviews — security requirements should be defined at design time, not patched afterward

## When Not to Apply
- Security controls should always be applied; the question is only degree of rigor proportionate to risk.

## Key Concepts
- **HTTPS Everywhere**: All API traffic must be encrypted in transit — no HTTP endpoints in production
- **Authentication**: Every API call must be authenticated — JWT bearer tokens (via OAuth2/OIDC), API keys, mTLS for service-to-service
- **Authorization**: Authenticated identity is not sufficient — verify the caller is authorized for the specific resource and action
- **Input Validation**: Validate all inputs at the API boundary — reject malformed, oversized, or unexpected inputs before processing
- **Rate Limiting**: Prevent abuse and DoS by limiting request rates per client — HTTP 429 Too Many Requests with `Retry-After` header
- **Sensitive Data in Responses**: Return only the data the caller is authorized to see — no over-fetching of sensitive fields
- **Versioning and Deprecation**: Old API versions with known vulnerabilities must be removed — security debt accumulates on deprecated endpoints
- **Security Headers**: CORS policy, `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`
- **API Gateway**: Centralizes auth, rate limiting, and SSL termination — services focus on business logic

## In Practice
API security is enforced at the API Gateway layer in Method microservices engagements — authentication and rate limiting centralized, not per-service. Per-resource authorization is enforced within each service (the gateway validates identity; the service validates permissions for the specific resource). Input validation at the API boundary prevents injection and unexpected behavior.

## Engineering Knowledge
💡 **Engineering Knowledge — API Security**: HTTPS always, authenticate every call, authorize every resource access. Don't rely on network location — an internal API can be abused from a compromised service. Validate all input at the boundary; reject anything unexpected. Rate-limit all endpoints. Centralize auth and rate-limiting at the API Gateway, but implement resource-level authorization in each service — the gateway can't know who owns which record. → `engineering-knowledge-repository/security/api-security.md`

## Related Entries
- [OAuth2/OIDC](oauth2-oidc.md) — the standard protocol for API authentication and authorization
- [RBAC](rbac.md) — role-based authorization at the API layer
- [OWASP Top Ten](owasp-top-ten.md) — covers the vulnerability classes that API security controls must address
- [API Gateway Pattern](../architectural-styles/api-gateway-pattern.md) — centralizes API security controls

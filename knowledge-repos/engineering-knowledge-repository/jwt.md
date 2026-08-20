---
id: jwt
tags: [protocol, security, backend, network]
surfaces-at: [nfr-requirements, nfr-design, application-design]
related: [api-security, rbac, zero-trust-security, secrets-management]
complexity: intermediate
---

# JWT — JSON Web Tokens

## What It Is
A compact, URL-safe token format for representing claims between two parties. A JWT consists of three Base64URL-encoded parts: a header (algorithm, type), a payload (claims — subject, expiry, roles), and a signature that allows the recipient to verify the token was issued by a trusted party. JWTs are stateless — the server can verify the token without a database lookup. Used widely in OAuth 2.0 and OpenID Connect flows.

## When to Apply
- Stateless API authentication where the server should not maintain session state
- Microservices where a single token needs to carry identity and authorization claims across service calls
- OAuth 2.0 / OIDC flows (access tokens, ID tokens)
- Claims-based authorization where roles or permissions are embedded in the token

## When Not to Apply
- When you need to invalidate tokens immediately (JWTs are valid until expiry — revocation requires additional infrastructure)
- Long-lived sessions where the inability to revoke is a security concern
- When opaque tokens (server-side session IDs) are sufficient and token inspection at the edge is not needed

## Key Concepts
- **Claims**: Key-value pairs in the JWT payload — `sub` (subject/user ID), `iat` (issued at), `exp` (expiry), `iss` (issuer), custom claims for roles/permissions
- **Signing Algorithms**: `RS256` (RSA + SHA-256, asymmetric — recommended for production) or `HS256` (HMAC + SHA-256, symmetric — simpler but requires shared secret). Never use `alg: none`
- **Access Token vs. Refresh Token**: Short-lived access tokens (15 min) + long-lived refresh tokens (days/weeks). Refresh tokens are opaque and stored server-side — can be revoked
- **JWT Verification**: Verify signature, expiry (`exp`), issuer (`iss`), and audience (`aud`) on every request. Never trust claims in an unverified JWT
- **Token Revocation**: JWTs cannot be revoked before expiry without a deny list. Use short expiry + refresh tokens to limit exposure window
- **JWT Libraries**: `jsonwebtoken` (Node.js), `java-jwt` (Auth0, Java), `PyJWT` (Python) — use well-audited libraries; never implement JWT crypto yourself
- **JWKS (JSON Web Key Sets)**: Public key endpoint published by auth server — services fetch JWKS to verify signatures without sharing secrets

## In Practice
Method uses JWTs with RS256 signing for API authentication. Access tokens are short-lived (15 minutes); refresh tokens are stored in HTTP-only cookies. JWKS endpoints are used for service-to-service signature verification. JWT claims carry user ID and roles for authorization. Token validation middleware runs on every request — verifying signature, expiry, issuer, and audience.

## Engineering Knowledge
💡 **Engineering Knowledge — JWT**: Short-lived access tokens (15 min) + opaque refresh tokens. Use RS256 (asymmetric) — publish JWKS so consumers verify without a shared secret. Always verify: signature, `exp`, `iss`, `aud`. Never use `alg: none`. JWTs can't be revoked before expiry — keep access token lifetimes short; revoke refresh tokens server-side. Embed roles/permissions in claims for stateless authorization at the API layer. Use a well-audited library — never roll your own JWT crypto. → `engineering-knowledge-repository/security/jwt.md`

## Related Entries
- [API Security](api-security.md) — JWT is the primary authentication mechanism for REST and GraphQL APIs
- [RBAC](rbac.md) — role claims in JWTs enable claims-based RBAC
- [Zero Trust Security](zero-trust-security.md) — short-lived JWTs support zero-trust credential rotation
- [Secrets Management](secrets-management.md) — signing keys must be stored and rotated as secrets

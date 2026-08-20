---
id: api-authentication-patterns
tags: [reference, api-design, security, backend, network]
surfaces-at: [application-design, nfr-requirements]
related: [jwt, oauth2-oidc, mtls, api-security, zero-trust-security, api-gateway-design]
complexity: intermediate
---

# API Authentication Patterns

## What It Is
A decision framework for choosing how API consumers prove their identity. API authentication is not one-size-fits-all — the right mechanism depends on who the caller is (human user, machine, third-party service), the sensitivity of the resource, and the trust model. Choosing the wrong mechanism creates either security gaps or unnecessary complexity.

## When to Apply
- During API design — authentication mechanism is a contract decision, not an implementation detail
- When onboarding a new type of consumer (partner integration, mobile client, service account)

## Key Concepts

**API Keys**
- A static secret string passed in a header (`X-API-Key`) or query parameter
- Simplest to implement; no expiry by default; no user identity — identifies an application, not a person
- Suitable for: server-to-server calls where the client is a trusted internal or partner system; public read-only APIs with rate limiting
- Risk: keys don't expire, are easy to leak, and provide no granular permission model
- Mitigations: rotate regularly, scope to minimum permissions, store in secrets manager, never in URLs

**OAuth 2.0 Client Credentials**
- Machine-to-machine flow: the client exchanges its `client_id` + `client_secret` for a short-lived access token
- Tokens expire (typically 1 hour); can carry scope claims; auditable; revocable
- Suitable for: internal service-to-service calls, partner integrations where the caller is a system not a user
- The right default for service-to-service authentication in most architectures

**OAuth 2.0 Authorization Code (+ PKCE)**
- User-delegated flow: the user authenticates with an identity provider and grants the client access on their behalf
- Suitable for: any API called on behalf of a human user (web apps, mobile apps, third-party integrations)
- PKCE (Proof Key for Code Exchange) is mandatory for public clients (mobile, SPA) — prevents authorization code interception

**JWT Bearer Tokens**
- A signed token carrying claims (user ID, roles, scopes) presented in `Authorization: Bearer <token>`
- Stateless — server verifies signature without a database lookup
- Issued by OAuth 2.0 / OIDC flows or custom auth servers
- Not an authentication mechanism itself — it is the token format used by OAuth flows

**mTLS (Mutual TLS)**
- Both client and server present certificates; the server verifies the client certificate against a trusted CA
- Strongest authentication for service-to-service calls — cryptographic identity, no shared secrets
- Higher operational overhead (certificate lifecycle management)
- Suitable for: zero-trust architectures, regulated industries, high-security service meshes

**Decision Matrix**:
| Caller Type | Recommended Mechanism |
|---|---|
| Human user (web/mobile) | OAuth 2.0 Authorization Code + PKCE |
| Internal service | OAuth 2.0 Client Credentials or mTLS |
| Partner system | OAuth 2.0 Client Credentials or API Key (with rotation policy) |
| Public read-only API | API Key with rate limiting |
| Zero-trust / regulated | mTLS |

## In Practice
Method defaults: OAuth 2.0 Client Credentials for service-to-service; Authorization Code + PKCE for user-facing APIs; JWT bearer tokens as the token format throughout. API keys are used only for low-sensitivity partner integrations with mandatory rotation policies. mTLS is applied in zero-trust service mesh deployments.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — API Authentication Patterns**: Match the mechanism to the caller. Human users: OAuth 2.0 Authorization Code + PKCE. Machine-to-machine: OAuth 2.0 Client Credentials (short-lived tokens, revocable, scoped). API keys are convenient but static — use only where token infrastructure is unavailable, and enforce rotation. mTLS is the strongest option for zero-trust service meshes. JWT is a token format, not an auth mechanism — it carries the result of an OAuth flow. Never roll your own auth. → `engineering-knowledge-repository/api-authentication-patterns.md`

## Related Entries
- [JWT](jwt.md) — the token format used in OAuth 2.0 flows
- [OAuth 2.0 / OIDC](oauth2-oidc.md) — the authorization framework underlying most API authentication patterns
- [mTLS](mtls.md) — mutual TLS for certificate-based service authentication
- [API Security](api-security.md) — authentication is one layer of the broader API security model
- [Zero Trust Security](zero-trust-security.md) — zero trust drives toward mTLS and short-lived credentials
- [API Gateway Design](api-gateway-design.md) — authentication is enforced at the gateway layer

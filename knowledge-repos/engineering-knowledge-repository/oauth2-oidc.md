---
id: oauth2-oidc
tags: [protocol, security, network, backend]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design, application-design]
related: [api-gateway-pattern, twelve-factor-app, microservices]
complexity: intermediate
---

# OAuth 2.0 and OpenID Connect (OIDC)

## What It Is
**OAuth 2.0** is an authorization framework that enables applications to obtain limited access to user accounts on third-party services without exposing credentials. It defines flows ("grants") for different client types — web apps, mobile apps, server-to-server — that result in access tokens authorizing specific scopes of access.

**OpenID Connect (OIDC)** is an identity layer built on top of OAuth 2.0 that adds authentication. Where OAuth 2.0 answers "is this token authorized to access this resource?", OIDC answers "who is this user?" OIDC introduces the ID Token (a JWT containing user identity claims) alongside the OAuth 2.0 access token.

Together, OAuth 2.0 + OIDC are the industry standard for delegated authorization and federated identity.

## When to Apply
- Any application with user authentication — OIDC is the standard protocol
- APIs that need to authorize access from external clients or third-party integrations — OAuth 2.0 scopes
- Microservices systems where service-to-service calls need authentication — Client Credentials grant
- Federated identity — allow users to authenticate via Google, GitHub, enterprise SSO (SAML bridged through OIDC)
- Multi-tenant SaaS systems requiring tenant-scoped authorization

## When Not to Apply
- Internal system-to-system calls within a trusted network where mutual TLS or API keys are sufficient
- Extremely simple single-user tools where session-based authentication is appropriate
- When the operational overhead of running an authorization server is not justified — consider a managed identity provider (Auth0, Okta, AWS Cognito, Azure AD)

## Key Concepts
- **OAuth 2.0 Flows (Grants)**:
  - *Authorization Code + PKCE*: The standard flow for web and mobile apps — user redirects to IdP, authorizes, gets a code, exchanges for tokens. Always use PKCE.
  - *Client Credentials*: Machine-to-machine (M2M) — service authenticates with client ID + secret to get an access token. No user involved.
  - *Device Code*: For devices with limited input (TVs, CLIs)
  - *Implicit flow (deprecated)*: Do not use — replaced by Authorization Code + PKCE
- **Access Token**: Short-lived token (typically JWT) authorizing access to a resource. Presented by the client on each request.
- **ID Token**: OIDC-specific JWT containing identity claims (sub, email, name). Consumed by the client — not sent to resource servers.
- **Refresh Token**: Long-lived token used to obtain new access tokens without re-authenticating the user
- **Scopes**: Strings that define what access an access token grants — "read:orders", "write:profile"
- **JWT (JSON Web Token)**: The encoding format for access and ID tokens — contains claims, signed by the issuer, verifiable by the resource server without calling back to the IdP
- **JWKS (JSON Web Key Set)**: The public keys the authorization server publishes so resource servers can verify JWT signatures
- **Identity Provider (IdP)**: The service that issues tokens — Auth0, Okta, AWS Cognito, Azure Entra ID, or self-hosted (Keycloak)

## In Practice
OAuth 2.0 + OIDC is the standard authentication and authorization stack in Method engineering engagements. The API Gateway validates access tokens centrally — services receive verified claims without needing to call the IdP per request. The managed IdP path (Auth0, Cognito, Okta) is preferred over self-hosted (Keycloak) unless client requirements mandate it. Token validation, scope enforcement, and refresh token rotation are infrastructure concerns, not application concerns — implement once at the gateway or shared middleware layer.

## Engineering Knowledge
💡 **Engineering Knowledge — OAuth 2.0 / OIDC**: OAuth 2.0 handles authorization (what can this token do?); OIDC adds authentication (who is this user?). Use Authorization Code + PKCE for user-facing apps, Client Credentials for M2M. Validate access tokens at the API Gateway — services trust the gateway's verified claims. Use a managed IdP (Auth0, Cognito, Okta) unless you have a reason to self-host. Never implement your own token issuance — the spec surface is too large to get right. → `engineering-knowledge-repository/security/oauth2-oidc.md`

## Related Entries
- [API Gateway Pattern](../architectural-styles/api-gateway-pattern.md) — the gateway is where token validation is centralized
- [Twelve-Factor App](../architectural-philosophy/twelve-factor-app.md) — credentials and client secrets are config, never code
- [Microservices](../architectural-styles/microservices.md) — service-to-service auth uses Client Credentials grant

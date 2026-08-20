---
id: session-management
tags: [pattern, security, backend, frontend]
surfaces-at: [application-design, functional-design]
related: [jwt, oauth2-oidc, encryption, cors, injection-attacks]
complexity: intermediate
---

# Session Management

## What It Is
The mechanisms for maintaining authenticated state between a user's initial login and their subsequent requests — including how session tokens are created, stored, transmitted, validated, and invalidated. Insecure session management is consistently in the OWASP Top 10 because the consequences are severe: session hijacking gives an attacker full access as the victim. Modern web applications use either stateful sessions (server-side session storage) or stateless tokens (JWTs), each with distinct security tradeoffs.

## When to Apply
- Every application with user authentication
- When implementing "remember me" or persistent login functionality
- When designing logout and session expiration behavior
- When handling authentication across subdomains or multiple applications

## Key Concepts
- **Session Tokens vs. JWTs**:
  - *Stateful sessions*: Server generates a random, opaque session ID stored server-side (Redis, database). Token maps to server-side session data. Instant revocation (delete the session record). Requires server-side storage; doesn't scale across services without shared session store
  - *Stateless JWTs*: Token contains the claims; server verifies the signature. No server-side lookup. Cannot be instantly revoked (token is valid until expiry). Scales across services with shared signing key. See [JWT](jwt.md)
- **Secure Cookie Attributes**: For cookie-based sessions, set all security attributes:
  - `HttpOnly`: Cookie inaccessible to JavaScript. Prevents XSS from stealing the session token. **Always set**
  - `Secure`: Cookie only sent over HTTPS. Prevents interception over HTTP. **Always set in production**
  - `SameSite=Strict` or `SameSite=Lax`: Prevents CSRF attacks by restricting cross-site cookie sending. `Lax` allows cookies on top-level navigations (following a link); `Strict` requires same-site origin
  - `Domain`: Scope cookie to appropriate domain/subdomain only
  - `Path`: Restrict cookie to relevant paths if appropriate
- **Session Fixation**: An attacker sets a known session token before the user logs in, then hijacks the session after login. Prevention: generate a new session ID upon successful login — never reuse the pre-authentication session ID
- **Session Expiration**:
  - *Absolute timeout*: Session expires after a fixed time regardless of activity (e.g., 8 hours). Required for high-security applications
  - *Idle timeout*: Session expires after inactivity (e.g., 30 minutes). Resets on each request
  - Both timeouts should be implemented for most applications
- **CSRF (Cross-Site Request Forgery)**: An attack where a malicious site makes a request to your application in the user's browser, using the user's session cookie. Prevention:
  - `SameSite` cookie attribute is the primary modern defense
  - CSRF tokens (synchronizer token pattern): server generates a token stored in the session and in a hidden form field or header; validates on state-changing requests. Required for `SameSite=None` or legacy browser compatibility
- **Secure Logout**: Logout must:
  1. Invalidate the server-side session (stateful) or add the token to a denylist (stateless)
  2. Clear the session cookie by setting it with `Max-Age=0` or `Expires` in the past
  3. Redirect to a page that doesn't display sensitive data from the pre-logout state
  - Logout that only clears the client-side cookie without invalidating the server-side session is incomplete — the token is still valid if captured
- **Token Storage in SPAs**: For SPAs:
  - *HttpOnly cookie*: Best security; not accessible to JavaScript; CSRF protection needed
  - *Memory (React state/store)*: Lost on page refresh; XSS can read from JS
  - *localStorage*: Persistent across page loads; XSS can steal tokens. Avoid for authentication tokens
  - Recommended: HttpOnly cookie with SameSite + CSRF token header

## In Practice
Method web applications use HttpOnly, Secure, SameSite=Lax cookies for session tokens. Sessions are stored in Redis with a 30-minute idle timeout and 8-hour absolute timeout. Session ID is regenerated on login (prevents session fixation). Logout invalidates the Redis session entry and clears the cookie. SPAs use the BFF (Backend for Frontend) pattern: the BFF holds the session cookie; the SPA communicates with the BFF, never directly holding authentication tokens.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Session Management**: Set `HttpOnly`, `Secure`, and `SameSite` on every session cookie — missing any of these is a known vulnerability. Regenerate the session ID on login — session fixation is a real, exploitable attack when you don't. Logout must invalidate the server-side session, not just clear the cookie — a captured cookie is still valid otherwise. For SPAs, the BFF pattern keeps authentication tokens off the frontend entirely — the browser only holds a session cookie, not a JWT it can be tricked into sending to an attacker's domain. → `engineering-knowledge-repository/session-management.md`

## Related Entries
- [JWT](jwt.md) — JWTs are an alternative to stateful sessions with different revocation and scaling tradeoffs
- [OAuth2 and OIDC](oauth2-oidc.md) — OAuth2/OIDC sessions involve access tokens and refresh tokens with their own management requirements
- [Encryption](encryption.md) — session data stored server-side should be encrypted at rest
- [CORS](cors.md) — CORS and SameSite cookie policies interact for cross-origin web application architectures
- [Injection Attacks](injection-attacks.md) — XSS attacks steal session tokens; session security is incomplete without XSS prevention

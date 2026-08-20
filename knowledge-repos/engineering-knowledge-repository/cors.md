---
id: cors
tags: [reference, api-design, security, backend, network, frontend]
surfaces-at: [application-design, nfr-requirements, code-generation]
related: [api-security, api-gateway-design, rest-constraints, api-authentication-patterns]
complexity: foundational
---

# CORS — Cross-Origin Resource Sharing

## What It Is
A browser security mechanism that controls which cross-origin HTTP requests are permitted. By default, browsers block requests from one origin (scheme + domain + port) to a different origin — the Same-Origin Policy. CORS is the standard by which servers opt in to allowing specific cross-origin requests via HTTP response headers. It is a browser enforcement mechanism — it does not protect server-to-server communication.

## When to Apply
- Any API consumed by a web frontend hosted on a different origin (almost all production APIs)
- Single-page applications calling backend APIs
- Third-party JavaScript integrations (widgets, SDKs) calling your API from consumer websites

## When Not to Apply
- Server-to-server API calls — CORS is irrelevant; there is no browser enforcing it
- APIs only consumed by native mobile apps — no browser, no CORS

## Key Concepts
- **Simple Requests**: GET, POST, or HEAD requests with safe headers and content types (`application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`). The browser sends the request and checks the response headers — no preflight
- **Preflighted Requests**: Requests with custom headers, JSON bodies, or non-simple methods (PUT, DELETE, PATCH). The browser sends an `OPTIONS` request first — the preflight — to check if the actual request is permitted. Only sends the real request if the server approves
- **`Access-Control-Allow-Origin`**: The core CORS header. `*` allows all origins (no credentials). A specific origin (`https://app.example.com`) allows only that origin. Must reflect the requesting origin dynamically for credentialed requests
- **`Access-Control-Allow-Credentials: true`**: Required to allow requests with cookies or `Authorization` headers. Cannot be combined with `Access-Control-Allow-Origin: *` — a specific origin must be specified
- **`Access-Control-Allow-Methods`**: Which HTTP methods are permitted — `GET, POST, PUT, DELETE, OPTIONS`
- **`Access-Control-Allow-Headers`**: Which request headers are permitted — `Authorization, Content-Type, X-Correlation-ID`
- **`Access-Control-Max-Age`**: How long (in seconds) the preflight response can be cached — reduces preflight round trips. `86400` (24 hours) is a common value
- **`Access-Control-Expose-Headers`**: Headers the browser is allowed to expose to JavaScript — by default only a safe subset. Required to expose custom headers like `X-RateLimit-Remaining`
- **Common Misconfiguration**: Reflecting any origin dynamically without validation (`Access-Control-Allow-Origin: <whatever the request sent>`) effectively disables CORS protection. Always validate the origin against an allowlist before reflecting it

## In Practice
Method configures CORS at the API gateway or middleware layer — not in individual services. Allowed origins are defined per environment (dev allows localhost variants; production allows specific domains). Credentials are enabled only where required. `Access-Control-Max-Age: 86400` reduces preflight overhead. Custom response headers exposed to clients are enumerated in `Access-Control-Expose-Headers`.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — CORS**: CORS is browser-enforced, not server-enforced — it doesn't protect your API from non-browser clients. Configure it at the gateway. Never use `Access-Control-Allow-Origin: *` with `Access-Control-Allow-Credentials: true` — browsers will reject it. Never reflect any arbitrary origin without an allowlist check — that defeats the entire mechanism. Cache preflight responses with `Access-Control-Max-Age` to avoid an OPTIONS round trip on every credentialed request. Expose custom headers explicitly with `Access-Control-Expose-Headers` or JavaScript won't be able to read them. → `engineering-knowledge-repository/cors.md`

## Related Entries
- [API Security](api-security.md) — CORS is one layer of web API security
- [API Gateway Design](api-gateway-design.md) — CORS headers belong in the gateway layer, not individual services
- [REST Constraints](rest-constraints.md) — CORS operates on HTTP request/response semantics
- [API Authentication Patterns](api-authentication-patterns.md) — credentialed CORS requests carry authentication tokens

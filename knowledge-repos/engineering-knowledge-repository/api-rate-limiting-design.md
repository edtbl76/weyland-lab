---
id: api-rate-limiting-design
tags: [pattern, api-design, security, backend, network]
surfaces-at: [nfr-requirements, application-design, infrastructure-design]
related: [api-security, api-gateway-design, error-response-standards, rest-constraints]
complexity: intermediate
---

# API Rate Limiting Design

## What It Is
The practice of restricting how many requests a client can make to an API within a given time window. Rate limiting protects services from abuse, prevents runaway clients from degrading service for others, and enables fair resource allocation. Well-designed rate limiting is transparent — clients receive headers telling them their current quota and when it resets, so they can adapt their behavior rather than being surprised by failures.

## When to Apply
- All public-facing and partner-facing APIs
- Internal APIs where a misbehaving consumer could degrade service for others
- Any endpoint where unconstrained usage creates cost or availability risk

## Key Concepts
- **Token Bucket**: The most common algorithm. Each client has a bucket of N tokens. Each request consumes one token. Tokens refill at a fixed rate. Allows short bursts up to bucket capacity, then throttles to the refill rate. Implemented in Redis with atomic operations
- **Sliding Window**: Tracks request count within a rolling time window. More accurate than fixed windows (no burst at window boundary). Higher memory cost than token bucket
- **Fixed Window**: Simplest — count requests in a fixed time slot (per minute, per hour). Burst vulnerability: a client can double their rate by sending at the end of one window and the start of the next
- **Rate Limit Headers**: Include on every response:
  - `X-RateLimit-Limit: 1000` — requests allowed per window
  - `X-RateLimit-Remaining: 743` — requests remaining in current window
  - `X-RateLimit-Reset: 1704067200` — Unix timestamp when the window resets
- **`429 Too Many Requests`**: The correct status code when a client exceeds their limit
- **`Retry-After` Header**: Returned with 429 — tells the client how many seconds to wait before retrying
- **Rate Limit Scoping**: Per API key, per user, per IP, per endpoint, or combinations. Granular scoping prevents one expensive endpoint from consuming the whole quota
- **Burst Allowance**: Allow short bursts above the steady-state rate (token bucket naturally handles this). Makes the API more usable for bursty but well-behaved clients
- **API Gateway Enforcement**: Rate limiting belongs in the API gateway or a shared middleware layer — not in individual service code

## In Practice
Method implements rate limiting at the API gateway layer (AWS API Gateway, Kong, or Nginx). Token bucket algorithm via Redis. Standard headers on all responses. Limits are tiered by client type (internal, partner, public). `429` responses include `Retry-After`. Rate limit configuration is per-route and per-client-tier, not global.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — API Rate Limiting Design**: Implement at the gateway layer — not in every service. Use token bucket (allows bursts, easy to implement in Redis). Return `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers on every response — clients that can see their quota don't get surprised by 429s. Return `Retry-After` with every 429. Scope limits per API key and per endpoint — an expensive search endpoint needs tighter limits than a simple GET. → `engineering-knowledge-repository/api-design/api-rate-limiting-design.md`

## Related Entries
- [API Security](../security/api-security.md) — rate limiting is a core API security control
- [API Gateway Design](api-gateway-design.md) — rate limiting belongs in the gateway layer
- [Error Response Standards](error-response-standards.md) — 429 responses should follow the RFC 7807 error format
- [REST Constraints](rest-constraints.md) — HTTP status code semantics for rate limit responses

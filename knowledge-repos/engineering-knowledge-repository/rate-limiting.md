---
id: rate-limiting
tags: [pattern, performance, reliability, api-design, security]
surfaces-at: [application-design, functional-design, nfr-design]
related: [api-gateway-design, backpressure, circuit-breaker, caching-strategies]
complexity: intermediate
---

# Rate Limiting

## What It Is
Controlling the rate at which a client or user can make requests to a service, enforcing upper bounds on request frequency to protect the service from overload, prevent abuse, and ensure fair resource allocation across clients. Without rate limiting, a single misbehaving or malicious client can consume all available capacity, degrading service for everyone else. Rate limiting is the boundary between an open API and a production-grade API.

## When to Apply
- Every public or partner-facing API
- Internal APIs between services where runaway clients could cause cascading failures
- Any endpoint susceptible to brute-force attacks (auth, password reset)
- Paid API tiers where usage must be metered and enforced

## Key Concepts
- **Rate Limiting Algorithms**:
  - *Token Bucket*: A bucket holds up to N tokens; tokens are added at a fixed rate; each request consumes one token. Allows bursting (use accumulated tokens) up to bucket size. Most common algorithm for API rate limiting — handles bursty traffic naturally
  - *Leaky Bucket*: Requests are queued and processed at a fixed rate regardless of arrival rate. Smooths bursts into steady output. Used in traffic shaping; uncommon for direct API rate limiting
  - *Fixed Window*: Count requests in fixed time windows (100 requests per minute). Simple; susceptible to boundary attacks — clients can double-rate at window transitions (50 at end of window + 50 at start of next)
  - *Sliding Window*: Tracks requests over a rolling time window. Eliminates boundary attacks; more expensive to implement. Redis sorted sets or approximate counters (sliding window log, sliding window counter)
- **Rate Limit Dimensions**:
  - *Per client/API key*: Most common. Each API key has an independent quota
  - *Per user*: For authenticated endpoints; quota tied to the authenticated user identity
  - *Per IP*: For unauthenticated endpoints; susceptible to evasion behind NAT or proxies
  - *Global*: System-wide limit regardless of client — protects against DDoS from many sources
- **Response Headers**: Communicate rate limit status to clients:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Requests remaining in current window
  - `X-RateLimit-Reset`: Unix timestamp when the window resets
  - `Retry-After`: Seconds until the client may retry (on 429 response)
- **HTTP 429 Too Many Requests**: The correct status code for rate limit violations. Include a `Retry-After` header so well-behaved clients know when to retry
- **Implementation Locations**:
  - *API Gateway*: AWS API Gateway, Kong, nginx — enforce rate limits before requests reach application code. Preferred for external APIs
  - *Application middleware*: Express rate-limit, Django REST framework throttling, FastAPI rate limiting. Easier to implement custom logic; runs after network stack
  - *Redis-backed*: Distributed rate limiting using Redis atomic operations (INCR + EXPIRE or sorted sets). Required for multi-instance deployments — in-memory rate limiters don't work with multiple app instances
- **Tiered Limits**: Different clients get different limits based on plan tier. Free: 100/hour; Pro: 1000/hour; Enterprise: custom. Implement via API key metadata or JWT claims
- **Graceful Degradation**: When rate limited, the service should return 429 immediately (don't queue indefinitely) with a clear error message and Retry-After header. Don't return 500 or time out
- **Distributed Rate Limiting**: Single-instance in-memory counters don't work when the service scales horizontally. Use Redis INCR with TTL for simple cases; Lua scripts or SETNX patterns for atomic token bucket implementations

## In Practice
Method uses AWS API Gateway for rate limiting on all public APIs — configurable per API key with tiered limits by plan. Internal service-to-service rate limiting uses Redis-backed token bucket middleware in FastAPI and Express. Auth endpoints (login, password reset) have strict per-IP limits (10/minute). All rate-limited responses include `X-RateLimit-*` headers and `Retry-After`. Limit breaches are logged and aggregated for abuse detection.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Rate Limiting**: Apply rate limiting at the API gateway layer for external APIs — it's simpler, more performant, and prevents load from reaching application servers. In-memory rate limiters don't work with horizontal scaling — use Redis with atomic operations. Always return `Retry-After` in 429 responses; clients that back off and retry properly are a sign of a well-designed API. Different limit dimensions serve different purposes: per-IP for DDoS protection, per-API-key for quota enforcement, per-user for fair use. Token bucket is the right algorithm for most cases — it allows short bursts without permanently punishing bursty clients. → `engineering-knowledge-repository/rate-limiting.md`

## Related Entries
- [API Gateway Design](api-gateway-design.md) — API gateways are the standard enforcement point for rate limiting external APIs
- [Backpressure](backpressure.md) — rate limiting is a client-facing form of backpressure — explicitly signaling capacity limits
- [Circuit Breaker](circuit-breaker.md) — circuit breakers protect services from downstream failures; rate limiting protects services from upstream overload
- [Caching Strategies](caching-strategies.md) — caching reduces origin load, complementing rate limiting as a protection mechanism

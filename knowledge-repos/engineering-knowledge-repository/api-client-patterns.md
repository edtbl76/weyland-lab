---
id: api-client-patterns
tags: [pattern, api-design, reliability, backend]
surfaces-at: [functional-design, code-generation]
related: [retry-pattern, circuit-breaker, idempotency, api-rate-limiting-design, api-observability, timeout-patterns]
complexity: intermediate
---

# API Client Patterns

## What It Is
Design patterns for building robust HTTP API clients — the consuming side of an API. A naive API client that makes a single request and throws on failure is fragile in production. Robust clients handle transient failures gracefully, respect rate limits, time out predictably, propagate correlation IDs for traceability, and surface actionable errors. These patterns apply whether building an internal service client or integrating a third-party API.

## When to Apply
- Building any HTTP client that calls an external or internal API
- Integrating third-party APIs (payment processors, data providers, external services)
- Service-to-service HTTP calls in microservice architectures

## Key Concepts
- **Retry with Exponential Backoff**: Retry on transient failures (5xx, network timeouts) with exponentially increasing delays — base delay × 2^attempt. Prevents thundering herd when a downstream service recovers. Only retry idempotent operations (GET, PUT, DELETE) or operations with idempotency keys. Do not retry on 4xx (client errors — retrying won't help)
- **Jitter**: Add random variance to retry delays — prevents synchronized retry storms when many clients fail simultaneously. `delay = base * 2^attempt + random(0, base)`
- **Retry Budget**: Limit total retry attempts (3-5) and total retry duration. Unbounded retries cause cascading failures. Use a maximum retry duration rather than just a count
- **Timeouts — Two Levels**:
  - *Connection timeout*: How long to wait to establish a connection (2-5 seconds)
  - *Read timeout*: How long to wait for the response after connection is established (based on expected operation duration)
  - Always set both — an absent read timeout means a hung server hangs your client indefinitely
- **Circuit Breaker**: After N consecutive failures, open the circuit — stop sending requests and return a fast failure immediately. After a cooldown period, allow a probe request. If it succeeds, close the circuit. Prevents a degraded downstream from overwhelming your service with slow failing requests. See Circuit Breaker entry
- **Idempotency Keys**: For non-idempotent operations (POST), send a client-generated idempotency key header. If retrying, reuse the same key — the server deduplicates. Enables safe retry of creation operations
- **Correlation ID Propagation**: Forward the incoming `X-Correlation-ID` header to all downstream API calls. Enables end-to-end request tracing across service boundaries
- **Response Validation**: Validate API responses against expected schema before using the data — don't assume the response is well-formed. Fail explicitly on unexpected response shapes
- **Error Classification**: Distinguish error types for correct handling:
  - *Retryable*: 429 (rate limited — respect Retry-After), 500/503 (transient server error)
  - *Non-retryable*: 400/422 (fix the request), 401 (reauthenticate), 403 (access denied), 404 (resource doesn't exist)
- **Rate Limit Handling**: Respect `Retry-After` and `X-RateLimit-Remaining` headers. Back off proactively when approaching limits, not just after 429s. Track rate limit consumption across concurrent requests

## In Practice
Method service clients use a shared HTTP client wrapper that applies retry with exponential backoff + jitter, enforces connection and read timeouts, propagates correlation IDs, and logs all requests with latency and status code. Circuit breakers (Resilience4j for Java, tenacity for Python) wrap calls to critical dependencies. Idempotency keys are generated client-side for all POST operations that create resources.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — API Client Patterns**: Always set both connection and read timeouts — a missing read timeout means a slow server hangs your thread indefinitely. Retry on 5xx and network errors with exponential backoff + jitter; never retry on 4xx. Add jitter to prevent synchronized retry storms. Only retry idempotent operations — use idempotency keys for POST retries. Propagate correlation IDs to every downstream call. Wrap calls to critical dependencies in a circuit breaker — fast failure is better than slow cascading failure. Classify errors before deciding to retry, log, or alert. → `engineering-knowledge-repository/api-client-patterns.md`

## Related Entries
- [Retry Pattern](retry-pattern.md) — detailed retry strategies including backoff algorithms
- [Circuit Breaker](circuit-breaker.md) — protecting services from cascading failures via degraded dependencies
- [Idempotency](idempotency.md) — idempotency keys enable safe retry of non-idempotent operations
- [API Rate Limiting Design](api-rate-limiting-design.md) — client-side rate limit handling complements server-side enforcement
- [API Observability](api-observability.md) — client-side request logging feeds into distributed tracing
- [Timeout Patterns](timeout-patterns.md) — timeout configuration strategies for distributed systems

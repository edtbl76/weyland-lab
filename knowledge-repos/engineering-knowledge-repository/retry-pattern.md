---
id: retry-pattern
tags: [pattern, reliability, backend, distributed-systems]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [circuit-breaker, bulkhead-pattern, dead-letter-queue]
complexity: foundational
---

# Retry Pattern

## What It Is
A resilience pattern that automatically re-attempts a failed operation, on the assumption that transient failures (brief network blips, momentary service unavailability, rate limiting) will resolve on their own. The retry policy specifies how many times to retry, how long to wait between retries, and under what conditions to retry vs. fail immediately.

## When to Apply
- Network calls to external services or APIs where transient failures are expected
- Message processing where occasional delivery failures occur
- Database operations under temporary lock contention or connection exhaustion
- Cloud API calls subject to rate limiting (HTTP 429, HTTP 503)

## When Not to Apply
- Non-idempotent operations — retrying a payment charge or email send without idempotency guarantees creates duplicate side effects
- Business errors (HTTP 400, 404, 422) — these are not transient; retrying won't help
- When the downstream service is known to be down — use Circuit Breaker to avoid retry storms
- When latency is critical and retries would unacceptably delay the caller

## Key Concepts
- **Transient vs. Permanent Failure**: Retry only transient failures (network timeout, 503). Never retry permanent failures (invalid input, 404, auth failure).
- **Exponential Backoff**: Double the wait time between each retry attempt — reduces thundering herd when many clients retry simultaneously
- **Jitter**: Add randomness to backoff intervals — prevents synchronized retry spikes when many clients fail at the same time
- **Max Retries**: Bound the retry count — infinite retries become an infinite loop
- **Idempotency**: Retried operations must be safe to execute multiple times — the downstream must handle duplicate calls correctly
- **Retry Budget**: Limit the percentage of requests that can be retrying at any given time — prevents a slow dependency from causing a retry storm
- **Retry Storm**: When many clients retry simultaneously against a struggling service, amplifying load instead of relieving it — mitigated by backoff + jitter + circuit breaker

## In Practice
Retry is the most basic resilience primitive in distributed systems. In Method engagements, retry policies are defined as part of NFR Design and applied via HTTP client configuration, message consumer retry policies, or service mesh rules. Retry should always be paired with Circuit Breaker — the circuit breaker trips when retries are consistently failing, preventing retry storms. Libraries: Resilience4j (JVM), Polly (.NET), retry decorators in cloud SDKs.

## Engineering Knowledge
💡 **Engineering Knowledge — Retry Pattern**: Transient failures are normal in distributed systems — networks blip, services hiccup. Retry automatically, but do it right: exponential backoff + jitter prevents synchronized retry storms, and only retry idempotent operations. Pair with Circuit Breaker — when retries are failing consistently, stop trying and fail fast. Never retry business errors (400, 404) — those won't get better. → `engineering-knowledge-repository/infrastructure/retry-pattern.md`

## Related Entries
- [Circuit Breaker](circuit-breaker.md) — trips when retries consistently fail, preventing retry storms
- [Bulkhead Pattern](bulkhead-pattern.md) — isolates retry storms to bounded resource pools
- [Dead Letter Queue](dead-letter-queue.md) — where messages go after all retries are exhausted

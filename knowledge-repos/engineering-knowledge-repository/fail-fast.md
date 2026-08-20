---
id: fail-fast
tags: [principle, backend, reliability]
surfaces-at: [application-design, functional-design]
related: [circuit-breaker, input-validation, error-response-standards, graceful-degradation]
complexity: foundational
---

# Fail Fast

## What It Is
A design principle that advocates detecting and reporting errors at the earliest possible point rather than allowing invalid or inconsistent state to propagate through a system. A system that fails fast produces an immediate, clear error when it encounters invalid input, broken configuration, or a violated assumption — rather than continuing to operate in a degraded or undefined state, potentially producing silent corruption or a harder-to-diagnose failure much later. Fail fast is the opposite of defensive programming that silently masks problems; it is aggressive about surfacing errors at the boundary where they originate.

## When to Apply
- Input validation at system and API boundaries — reject invalid requests immediately
- Service startup: validate configuration, verify database connectivity, and check required dependencies before accepting traffic
- Configuration loading: crash immediately if required environment variables are missing rather than failing on first use
- Any state that has preconditions: assert them at entry, not silently fail inside
- Distributed systems where propagating a bad request to downstream services compounds the damage

## Key Concepts
- **Fail at the Boundary**: Errors are cheapest to handle where they enter the system. An invalid API request detected at the HTTP layer is a single log line and a 400 response. The same invalid data discovered after being stored in the database and sent to a downstream service requires forensic debugging and compensating transactions
- **Startup Validation**: Services should validate their complete configuration and connectivity at startup. Missing environment variables, invalid credentials, and unreachable databases should cause immediate startup failure with a clear error message — not a running service that fails on first use. This surfaces deployment configuration errors at deploy time, not at the moment a user hits the endpoint
- **Assertions and Preconditions**: In code, assert preconditions at the entry of functions that require valid state: `assert user is not None`, `assert amount > 0`. In production code, replace assertions with explicit guard clauses that raise appropriate exceptions with informative messages. Do not silently return `None` or `0` when the input is invalid
- **Circuit Breaker**: The circuit breaker pattern is fail-fast at the infrastructure level — when a downstream service is failing, stop sending requests to it immediately (fail fast) rather than queuing requests that will all timeout. Prevents cascading failures
- **Contrast with Defensive Programming**: Defensive programming writes code that handles any input without crashing — useful for public library APIs and user-facing edge cases. Fail fast is appropriate for internal system boundaries, where a caller passing invalid state indicates a programming error that should be surfaced immediately
- **Fail Fast in Distributed Systems**: In a chain of services, a request with a missing required field should be rejected by the first service (fail fast), not forwarded to the third service where the error manifests as a confusing internal error. Define and validate contracts at service boundaries
- **"Let It Crash"**: The Erlang/OTP philosophy extends fail fast to process management — let individual processes crash on unexpected errors; the supervisor restarts them cleanly. This is a more aggressive application of fail fast: don't try to handle all errors locally; fail cleanly and let the system recover

## In Practice
Method API services validate all required fields at the request layer before any business logic runs — invalid requests return 400 with structured error details immediately. Service startup validates all required environment variables and database connectivity; services that fail startup checks emit a clear error log and exit with a non-zero code. Kubernetes liveness probes detect services that have started but entered a broken state. Circuit breakers prevent request buildup against failing dependencies.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Fail Fast**: Silent failures are the worst failures — they let invalid state propagate, corrupt data, and produce errors that are spatially and temporally distant from their cause. Fail loud and fail early: reject invalid inputs at the boundary, crash at startup on missing configuration, assert preconditions in code that requires valid state. The goal is a system where every failure produces an immediate, actionable error — not one that accumulates and surfaces as a mystery two layers deeper. The cost of a loud early failure is a clear error message; the cost of a silent late failure is hours of debugging. → `engineering-knowledge-repository/fail-fast.md`

## Related Entries
- [Circuit Breaker](circuit-breaker.md) — the circuit breaker applies fail-fast at the infrastructure level for downstream service failures
- [Input Validation](input-validation.md) — input validation is the primary application of fail-fast at system boundaries
- [Error Response Standards](error-response-standards.md) — failing fast produces errors that must be communicated clearly to callers
- [Graceful Degradation](graceful-degradation.md) — graceful degradation is the complement to fail fast: degrade non-critical paths; fail fast on critical ones

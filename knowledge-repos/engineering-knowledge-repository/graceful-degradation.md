---
id: graceful-degradation
tags: [pattern, reliability, backend]
surfaces-at: [application-design, functional-design]
related: [circuit-breaker, bulkhead-pattern, feature-flags, timeout-patterns, retry-pattern]
complexity: intermediate
---

# Graceful Degradation

## What It Is
Designing a service to continue operating at reduced functionality when a dependency is unavailable, slow, or returning errors — rather than propagating the failure to the user as a complete outage. A service that degrades gracefully serves a diminished but useful experience during partial failures; a service without graceful degradation turns every dependency failure into a user-facing outage. The goal is to isolate failure scope: a recommendation engine being down should not prevent a user from completing checkout.

## When to Apply
- Services with multiple independent features backed by different dependencies
- Non-critical dependencies (recommendations, personalization, analytics) that should not block core user flows
- Any service where partial availability is better than complete unavailability
- High-traffic services where dependency failures are statistically certain over time

## Key Concepts
- **Identify Critical vs. Non-Critical Dependencies**:
  - *Critical*: Failures block the primary user action. Payment processor for checkout; auth service for login. Cannot degrade — must fail or handle via circuit breaker
  - *Non-critical*: Failures degrade quality but don't block the primary action. Product recommendations; social proof widgets; A/B test assignments; analytics events. Degrade with fallback
- **Fallback Strategies**:
  - *Default/empty response*: Return an empty list, a default value, or a "no results" state instead of an error
  - *Cached data*: Serve a stale cached response if the live dependency is unavailable. Explicitly prefer stale-but-available over fresh-but-unavailable for non-critical data
  - *Feature disable*: Suppress the feature entirely (hide the recommendations widget) rather than showing an error
  - *Static fallback*: Serve pre-defined fallback content (top-10 static recommendations) when dynamic recommendations fail
  - *Simplified logic*: Execute a simpler code path that doesn't require the dependency (rule-based recommendations instead of ML-based)
- **Circuit Breaker Integration**: Graceful degradation defines *what* to do when a dependency fails. Circuit breakers implement *when* to stop calling the dependency. They are complementary: the circuit breaker detects failure; graceful degradation provides the fallback behavior when the breaker is open
- **Feature Flags for Runtime Degradation**: Feature flags can force graceful degradation intentionally — disable a non-critical feature flag before a risky deployment, or as an emergency lever when a dependency is known to be degraded. See [Feature Flags](feature-flags.md)
- **User Communication**: When features are degraded, communicate clearly — "Personalized recommendations are temporarily unavailable." Silence is confusing; a clear message manages expectations
- **Testing Degradation Paths**: Graceful degradation logic is only as good as its tests. Use fault injection or mock failure modes in integration tests to verify that the fallback path executes correctly and returns a valid degraded response (not a 500)
- **Dependency Timeout Budgets**: Non-critical dependencies should have aggressive timeouts — if recommendations don't return in 100ms, skip them. The primary user flow must not wait for a non-critical dependency
- **Downstream Impact**: Graceful degradation of writes (analytics events, audit logs) requires buffering or fire-and-forget patterns. Don't block user-facing writes on analytics systems

## In Practice
Method services categorize dependencies as critical or non-critical at the architecture review stage. Non-critical dependency calls are wrapped with timeout budgets (100-200ms) and fallback logic (empty response or cached stale data). Circuit breakers from Resilience4j or Python's `tenacity` protect all external calls. Feature flags (LaunchDarkly) provide on-demand degradation toggles for operational control. Degraded-mode behavior is tested via integration tests with mocked dependency failures.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Graceful Degradation**: Map your dependencies before you code them: which ones block the core user action, and which ones enhance it? Non-critical dependencies must have aggressive timeouts and fallback behavior defined before they ship. A recommendations service that takes 3 seconds and returns nothing on failure should return an empty list in 100ms — users notice 3-second hangs more than empty recommendation widgets. Test your fallback paths explicitly — degradation code that is never executed in tests is degradation code that breaks in production. Pair graceful degradation with feature flags for operational control during incidents. → `engineering-knowledge-repository/graceful-degradation.md`

## Related Entries
- [Circuit Breaker](circuit-breaker.md) — circuit breakers detect when to stop calling a dependency; graceful degradation defines what to do instead
- [Bulkhead Pattern](bulkhead-pattern.md) — bulkheads isolate failure scope; graceful degradation defines the behavior in each isolated compartment
- [Feature Flags](feature-flags.md) — feature flags provide runtime control over graceful degradation modes
- [Timeout Patterns](timeout-patterns.md) — aggressive timeouts on non-critical dependencies are prerequisite to graceful degradation
- [Retry Pattern](retry-pattern.md) — retries are appropriate for transient failures; graceful degradation is appropriate for sustained dependency unavailability

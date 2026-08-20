---
id: bulkhead-pattern
tags: [pattern, reliability, distributed-systems, backend]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [circuit-breaker, retry-pattern, microservices]
complexity: intermediate
---

# Bulkhead Pattern

## What It Is
A resilience pattern that isolates elements of a system into pools so that if one fails or becomes saturated, the others continue to function. Named after the watertight compartments (bulkheads) in a ship's hull — a breach in one compartment doesn't sink the whole ship. In software, bulkheads typically isolate thread pools, connection pools, or resource limits per downstream dependency or customer tier so that a slow or failing dependency cannot exhaust shared resources and bring down the entire service.

## When to Apply
- Services that call multiple downstream dependencies — isolate each dependency's resource pool
- Multi-tenant systems where one tenant's high load should not degrade others
- Critical vs. non-critical workloads in the same service — give critical paths their own resource pool
- High-traffic systems where one slow downstream call could exhaust the global thread pool

## When Not to Apply
- Simple single-dependency services — one pool is fine
- Very low traffic services where resource contention is not a realistic failure mode
- When the overhead of managing separate pools outweighs the isolation benefit

## Key Concepts
- **Thread Pool Isolation**: Each downstream dependency or workload gets its own bounded thread pool. If dependency A is slow, only its pool fills up — other dependencies are unaffected.
- **Connection Pool Isolation**: Separate database or HTTP connection pools per downstream service or tenant
- **Semaphore Isolation**: A lighter alternative to thread pools — limits concurrent calls without a separate thread (lower overhead, less isolation)
- **Fail Fast**: When a bulkhead pool is full, new requests fail immediately rather than queuing indefinitely
- **Graceful Degradation**: With bulkheads, partial failures degrade specific capabilities rather than the whole system
- **Hystrix / Resilience4j**: Common JVM libraries for bulkhead implementation; cloud-native alternatives include Istio service mesh bulkheads

## In Practice
Bulkhead is a standard resilience pattern in Method microservices engagements, typically paired with Circuit Breaker for a complete fault-tolerance strategy. The most common implementation is thread pool isolation for outbound HTTP calls to distinct downstream services. In multi-tenant SaaS systems, bulkheads also apply at the tenant level to prevent "noisy neighbor" problems. Bulkhead configuration (pool sizes, semaphore limits) requires load-testing to tune correctly.

## Engineering Knowledge
💡 **Engineering Knowledge — Bulkhead Pattern**: A slow downstream call shouldn't take down your whole service. Assign each downstream dependency its own resource pool (thread pool or semaphore) so that exhaustion in one pool doesn't starve others. Pair with Circuit Breaker: bulkheads contain damage, circuit breakers stop the bleeding. In multi-tenant systems, apply bulkheads per tenant to prevent noisy-neighbor failures. → `engineering-knowledge-repository/infrastructure/bulkhead-pattern.md`

## Related Entries
- [Circuit Breaker](circuit-breaker.md) — the complementary pattern: circuit breakers trip when a dependency fails; bulkheads limit resource consumption
- [Retry Pattern](retry-pattern.md) — retry + bulkhead together prevent retry storms from exhausting isolated pools
- [Microservices](../architectural-styles/microservices.md) — bulkheads are essential resilience infrastructure for microservices

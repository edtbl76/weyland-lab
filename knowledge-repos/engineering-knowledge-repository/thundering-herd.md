---
id: thundering-herd
tags: [pattern, reliability, performance, backend]
surfaces-at: [application-design, nfr-design]
related: [caching-strategies, rate-limiting, circuit-breaker, connection-pooling, auto-scaling]
complexity: intermediate
---

# Thundering Herd

## What It Is
A failure mode where a large number of concurrent requests simultaneously attempt the same expensive operation — typically because a cache expires, a service restarts, or a popular resource becomes available — overwhelming the origin system. The "thundering herd" describes thousands of requests arriving in a burst, all missing the cache and hitting the database at once. What should be a temporary cache miss becomes a cascading failure as the database or origin service is flooded with identical requests simultaneously.

## When to Apply
- Any service with a shared cache where simultaneous expiry is possible
- Services that restart and immediately receive production traffic
- Popular resources with high read fan-out (product pages, user profiles, trending content)
- Any system where many concurrent clients wait on the same resource

## Key Concepts
- **Cache Stampede (Cache Dogpile)**: Many concurrent requests find the same cache key expired simultaneously. Each request independently queries the database, generating N identical expensive queries where N is the number of concurrent requests. The cache was working to absorb N queries/second; suddenly N hit the database at once
  - Mitigation: *Lock-based refresh* — only one request triggers the cache refresh; others wait or serve stale. Redis `SET NX` (set if not exists) implements a distributed lock for cache refresh. Only the "winner" fetches from origin; others wait briefly for the refreshed value
  - Mitigation: *Background refresh* — when the cache key is about to expire (within N seconds of TTL), a background job proactively refreshes it before it expires. The cache is never actually empty. More complex; excellent for high-traffic keys
  - Mitigation: *Stale-while-revalidate* — serve the stale value immediately while a background request refreshes it asynchronously. HTTP caching supports this natively; application caches can implement it
- **Jitter on TTL**: Cache keys with identical TTLs expire simultaneously, causing synchronized stampedes. Add random jitter to TTLs — instead of `TTL = 300s`, use `TTL = 300 + random(0, 60)` seconds. Staggers expirations across the cache population, spreading load over time
- **Service Restart Stampede**: When a service instance restarts after being down (crash, deployment), all accumulated demand hits it simultaneously before it's warm. Mitigations:
  - *Connection draining*: Load balancers stop sending new traffic before the instance is removed; traffic gradually shifts to remaining instances
  - *Slow start*: Load balancer gradually increases traffic to a newly started instance (AWS ALB slow start mode: ramp from 0% to 100% over 30-900 seconds)
  - *Warm-up period*: Pre-warm caches and connection pools before receiving full production traffic
- **Dog-pile Effect on Lock Contention**: Multiple threads or instances competing for the same lock (database row lock, Redis lock) generates contention. All blocked requests wake simultaneously when the lock is released. Mitigations: use FIFO queues, randomized backoff after lock acquisition failure
- **Event Fan-out**: When an event triggers processing for many subscribers simultaneously (a popular user posts content → 10 million followers' feeds update simultaneously). Mitigate with rate limiting the fan-out, processing in batches, or using a queue to spread processing over time

## In Practice
Method uses TTL jitter on all cache keys (±10-20% of base TTL). Redis-based lock-before-refresh is implemented for high-traffic cache keys where stampedes have caused incidents. AWS ALB slow start mode (60 second ramp) is enabled on all target groups. Connection draining is enabled for all ECS services. Background cache refresh runs for the top-100 most-accessed cache keys by hit rate.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Thundering Herd**: Add jitter to every cache TTL — synchronized expiry is a ticking time bomb on high-traffic systems. For the most-accessed cache keys, implement background refresh so the cache is never cold. When a service restarts, expect the thundering herd; enable ALB slow start or connection draining to ramp traffic gradually. Redis `SET NX` is the standard pattern for cache refresh locking — only one process pays the origin query cost; others wait briefly or serve stale. Thundering herd incidents often appear to be database capacity problems but are actually synchronization problems — fix the synchronization, not just the database capacity. → `engineering-knowledge-repository/thundering-herd.md`

## Related Entries
- [Caching Strategies](caching-strategies.md) — thundering herd is a cache failure mode; mitigation patterns are part of cache design
- [Rate Limiting](rate-limiting.md) — rate limiting constrains burst traffic that can cause thundering herd downstream
- [Circuit Breaker](circuit-breaker.md) — circuit breakers prevent cascading failures when the stampede overwhelms the origin
- [Connection Pooling](connection-pooling.md) — connection pool exhaustion is a common symptom of thundering herd hitting the database
- [Auto Scaling](auto-scaling.md) — auto-scaling can mitigate thundering herd effects by adding capacity, but scale-up latency means it cannot absorb instantaneous bursts

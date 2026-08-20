---
id: load-testing
tags: [methodology, testing, performance]
surfaces-at: [nfr-requirements, nfr-design]
related: [chaos-engineering, test-pyramid, horizontal-vs-vertical-scaling, caching-strategies]
complexity: intermediate
---

# Load Testing

## What It Is
Testing a system under expected and peak load conditions to validate that it meets performance requirements. Load testing verifies throughput, response time, and stability under concurrent users. Related variants: **Stress Testing** (push beyond expected limits to find breaking points), **Soak Testing** (sustained load over time to detect memory leaks and degradation), **Spike Testing** (sudden traffic surge to test auto-scaling and resilience).

## When to Apply
- Before go-live for any system with defined performance NFRs
- Before high-traffic events (product launches, campaigns, Black Friday)
- After significant architecture changes that could affect performance
- When establishing performance baselines to catch regressions

## When Not to Apply
- Low-traffic internal tools without performance requirements
- Early prototypes where performance optimization is premature
- Without defined performance acceptance criteria — load testing without targets produces data without meaning

## Key Concepts
- **VUs (Virtual Users)**: Simulated concurrent users executing requests — the primary load parameter
- **Throughput (RPS/TPS)**: Requests or transactions per second — how much load the system handles
- **Latency Percentiles**: p50, p95, p99 response times — tail latency matters for user experience; p99 is often 10x p50
- **Think Time**: Realistic pause between requests in user simulation — missing think time creates unrealistically high load
- **Warm-Up Period**: Allow the system to reach steady state before measuring — cold-start JIT compilation and cache warming skew early results
- **Ramp-Up**: Gradually increase load to the target level — sudden full load can produce misleading spike behavior
- **Tools**: k6 (modern, script-based), JMeter (GUI-based, extensive protocol support), Gatling (Scala DSL), Locust (Python), AWS Load Testing Solution

## In Practice
Load testing is a mandatory NFR validation step for any production system with availability SLAs at Method. k6 is the recommended tool — it's developer-friendly, integrates with CI pipelines, and produces clean output. Performance targets must be defined before testing (SLO-based: "99% of requests under 200ms at 500 concurrent users"). Performance tests belong in CI for regression detection on critical paths.

## Engineering Knowledge
💡 **Engineering Knowledge — Load Testing**: Define your performance targets before you test (p99 latency, throughput targets). Run load tests before go-live and before traffic events. k6 is the modern tool: script-based, CI-friendly, clean output. Watch p95/p99, not just p50 — tail latency is what users feel during peak traffic. Soak tests (sustained load over hours) catch memory leaks that short burst tests miss. No targets = no meaning. → `engineering-knowledge-repository/testing/load-testing.md`

## Related Entries
- [Chaos Engineering](chaos-engineering.md) — load testing validates performance; chaos testing validates resilience
- [Caching Strategies](../performance/caching-strategies.md) — caching is frequently the first optimization load testing exposes as needed
- [Horizontal vs. Vertical Scaling](../performance/horizontal-vs-vertical-scaling.md) — load test results inform the scaling strategy

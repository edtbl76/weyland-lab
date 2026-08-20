---
id: timeout-patterns
tags: [pattern, reliability, backend, distributed-systems]
surfaces-at: [nfr-requirements, functional-design]
related: [api-client-patterns, circuit-breaker, retry-pattern, bulkhead-pattern]
complexity: intermediate
---

# Timeout Patterns

## What It Is
Configuration and design strategies for bounding how long a system will wait for an operation to complete before giving up. Timeouts are a fundamental reliability control — without them, a slow or unresponsive dependency holds threads, connections, and memory indefinitely, eventually exhausting resources and causing cascading failure. Every network call, database query, and external service integration must have a timeout. The question is not whether to set timeouts but how to set them correctly.

## When to Apply
- Every outbound network call: HTTP requests, database queries, cache reads, message queue operations, external API calls
- Any operation that could hang indefinitely if the dependency is unresponsive
- Designing SLOs — timeouts define the worst-case latency your system tolerates from dependencies

## Key Concepts
- **Connection Timeout**: How long to wait to establish a connection. Catches unresponsive hosts and network partitions. Typically 1-5 seconds — if a connection can't be established quickly, the host is likely down
- **Read / Response Timeout**: How long to wait for the response after the connection is established. Must reflect expected operation duration — too short causes false timeouts on legitimately slow operations; too long allows slow dependencies to hold resources
- **Timeout Budgets**: Set timeouts relative to the caller's own SLO. If your endpoint has a 500ms SLO, your downstream calls must time out in < 500ms combined, leaving headroom for your own processing. Total timeout budget = SLO - local processing time
- **Cascading Timeout Propagation**: In a call chain A → B → C, A's timeout must be shorter than B's, which must be shorter than C's. Otherwise A times out while B and C are still processing work that will never be used — wasted resources. Propagate deadline context (gRPC deadlines, HTTP `X-Timeout` headers) through the chain
- **Deadline Propagation**: Pass the remaining time budget to downstream calls. If A has 200ms left when it calls B, B should know it has at most 200ms — not start a 5-second operation. gRPC deadlines implement this natively
- **Slow vs. Down**: A timeout distinguishes between "no response yet" and "explicitly failed." A timed-out operation may have partially succeeded on the server — treat as unknown state, not failure. For non-idempotent operations, a timeout requires careful error handling
- **Database Query Timeouts**: Set statement timeouts at the database driver level, not just application level. Prevents runaway queries from holding locks and consuming database resources. PostgreSQL: `statement_timeout`; MySQL: `MAX_EXECUTION_TIME`
- **Timeout vs. Circuit Breaker**: Timeouts bound individual operation duration. Circuit breakers stop sending requests when a dependency is consistently failing. They are complementary — use both

## In Practice
Method services set connection timeouts of 2-3 seconds and read timeouts based on p99 latency of the downstream service plus a 2-3x safety margin. Timeouts are configured per dependency, not globally. Database statement timeouts are set at the driver level. gRPC services propagate deadlines through call chains. Timeout values are reviewed when downstream SLOs change.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Timeout Patterns**: Every network call needs both a connection timeout and a read timeout — missing either means a hung dependency can hold your resources indefinitely. Set read timeouts based on the p99 latency of the downstream service plus a safety margin, not an arbitrary large number. Propagate deadline budgets through call chains — don't let downstream calls run longer than your own SLO allows. Set database statement timeouts at the driver level to prevent runaway queries from holding locks. Timeouts and circuit breakers are complementary: timeouts bound individual call duration; circuit breakers stop calls when a dependency is consistently failing. → `engineering-knowledge-repository/timeout-patterns.md`

## Related Entries
- [API Client Patterns](api-client-patterns.md) — timeouts are a core component of robust API client configuration
- [Circuit Breaker](circuit-breaker.md) — circuit breakers complement timeouts by stopping calls to consistently failing dependencies
- [Retry Pattern](retry-pattern.md) — timed-out requests may be retried; classify timeout as retryable with backoff
- [Bulkhead Pattern](bulkhead-pattern.md) — bulkheads isolate timeout-induced resource exhaustion from spreading across the system

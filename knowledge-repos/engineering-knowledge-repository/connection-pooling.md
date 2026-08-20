---
id: connection-pooling
tags: [pattern, performance, database, backend]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [horizontal-vs-vertical-scaling, database-indexing, caching-strategies]
complexity: intermediate
---

# Connection Pooling

## What It Is
A technique that maintains a pool of pre-established database connections that can be reused by multiple requests rather than creating and destroying a new connection for each request. Establishing a database connection is expensive (authentication, SSL handshake, memory allocation) — pooling amortizes this cost. Without pooling, high-concurrency applications quickly exhaust database connection limits.

## When to Apply
- Any application making database calls — connection pooling is a baseline practice, not an optimization
- Before scaling horizontally — each additional instance brings its own connection requirements; pool limits scale linearly without pooling at the proxy layer
- When database error logs show "too many connections" — a classic pooling problem indicator

## When Not to Apply
- Serverless functions with short bursts of execution — connection pooling in the function itself doesn't help (use PgBouncer as an external proxy instead)
- Very low-traffic applications making only occasional database calls — pooling overhead may not be worthwhile

## Key Concepts
- **Pool Size**: The number of connections maintained in the pool. Rule of thumb: (CPU cores × 2) + effective spindle count. Oversizing the pool wastes database resources; undersizing creates queueing.
- **Connection Reuse**: A request borrows a connection from the pool, uses it, and returns it — no connection creation overhead per request
- **Pool Exhaustion**: When all connections are in use and a new request needs one — it either waits (queue) or fails. Monitor pool utilization.
- **Application-Side Pool**: HikariCP (Java), pg-pool (Node.js), SQLAlchemy Pool (Python) — pooling within the application process
- **External Pool Proxy**: PgBouncer (PostgreSQL), ProxySQL (MySQL) — a standalone proxy between the application and database that pools connections at the infrastructure level. Essential for serverless and high-scale deployments.
- **Serverless + Pooling**: Each Lambda invocation creates a new connection without pooling — use RDS Proxy (AWS) or PgBouncer to prevent connection exhaustion

## In Practice
HikariCP is the standard JVM connection pool — used automatically by Spring Boot. For serverless (Lambda) + RDS workloads, RDS Proxy is Method's standard recommendation — it provides connection pooling at the infrastructure level, eliminating per-invocation connection overhead.

## Engineering Knowledge
💡 **Engineering Knowledge — Connection Pooling**: Creating a database connection is expensive. Reuse them. HikariCP (Java) and pg-pool (Node) pool connections within the application. For serverless functions, application-side pooling doesn't help — each invocation is a new process. Use RDS Proxy (AWS) or PgBouncer to pool at the infrastructure level. Right-size your pool: too small causes queuing, too large wastes database resources. Monitor pool utilization — exhaustion causes timeouts. → `engineering-knowledge-repository/performance/connection-pooling.md`

## Related Entries
- [Horizontal vs. Vertical Scaling](horizontal-vs-vertical-scaling.md) — scaling out multiplies connection requirements; external pool proxies address this
- [Caching Strategies](caching-strategies.md) — caching reduces database calls, reducing pool pressure

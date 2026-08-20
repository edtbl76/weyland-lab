---
id: apm
tags: [tooling, observability, performance, backend]
surfaces-at: [infrastructure-design, application-design]
related: [distributed-tracing, metrics-and-alerting, opentelemetry, real-user-monitoring, structured-logging]
complexity: intermediate
---

# APM (Application Performance Monitoring)

## What It Is
A category of observability tooling that automatically instruments applications to collect traces, metrics, and profiling data — providing visibility into request latency, error rates, database query performance, external API calls, and service dependencies. APM tools correlate this data across the full request lifecycle, from the frontend browser request through backend services to the database. The distinguishing feature of APM over raw metrics is the connection between a slow request and *why* it was slow — which query, which external call, which code path.

## When to Apply
- Any production service where latency or error rate matters
- When debugging performance issues that appear in metrics but require trace-level detail to diagnose
- Microservices architectures where request paths span multiple services
- Applications with complex database interactions where N+1 queries and slow queries are common

## Key Concepts
- **Auto-Instrumentation**: APM agents (Datadog, New Relic, Dynatrace) automatically instrument frameworks and libraries — Django, Express, Spring, Rails, SQLAlchemy, Postgres clients — without code changes. Traces and metrics flow automatically from application startup
- **Major APM Tools**:
  - *Datadog APM*: Traces, profiling, and error tracking. Integrates with Datadog infrastructure metrics, logs, and RUM for full-stack correlation. Strong AWS integration. The most common choice for AWS-heavy teams
  - *New Relic APM*: Full-stack observability; strong in Java and .NET ecosystems; competitive pricing for smaller teams
  - *Dynatrace*: AI-driven; automatic root cause analysis; strong in enterprise Java environments
  - *Elastic APM*: Open-source; integrates with the Elastic Stack (ELK). Good for teams already using Elasticsearch
  - *OpenTelemetry + Jaeger/Tempo*: Open-source, vendor-neutral tracing. More setup required; no commercial support. See [OpenTelemetry](opentelemetry.md) and [Distributed Tracing](distributed-tracing.md)
- **Key APM Metrics**:
  - *Request throughput*: Requests per second per service
  - *Error rate*: Percentage of requests resulting in errors
  - *Latency percentiles*: p50, p95, p99 — the distribution of response times
  - *Apdex score*: Satisfaction score combining fast, tolerable, and frustrated users into a single 0-1 metric
- **Flame Graphs and Profiling**: Continuous profiling captures stack traces across time, building flame graphs that show where CPU time is spent. Identifies hot paths, inefficient loops, and memory allocation patterns. Datadog Continuous Profiler, Pyroscope (open source)
- **Database Query Performance**: APM agents capture slow queries, N+1 query patterns, and total time spent in the database per request. Most teams find their biggest wins here — a single poorly indexed query can account for 80% of total request time
- **Service Map**: APM tools generate automatic service dependency maps showing which services call which, with error rates and latency for each edge. Essential for understanding microservice topology and identifying bottleneck services
- **APM Sampling**: Recording every trace at high throughput is expensive. APM tools implement sampling — head-based (sample decision at request start), tail-based (sample after seeing the full trace, biased toward slow/error requests), or adaptive. Configure sampling rates based on cost tolerance and traffic volume
- **Correlating Traces, Logs, and Metrics**: The true value of APM platforms is correlation — click from a slow trace to the associated logs; correlate a metrics spike with the traces that show what changed. OpenTelemetry's unified data model enables this across vendors

## In Practice
Method uses Datadog APM for all production services. Auto-instrumentation via Datadog agents handles traces and metrics collection. Service maps are used during architecture reviews and incident investigations. Slow query detection from APM traces is the primary input to database performance work. Continuous profiling is enabled on high-traffic services. Trace correlation with logs uses Datadog's trace ID injection into structured log output.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — APM**: APM traces are what turn "the service is slow" into "this specific database query is slow on every request that touches the user profile endpoint." Auto-instrumentation is worth its cost — the debugging time saved on the first production performance incident typically exceeds a year of APM licensing. The service map is underutilized: review it when designing new services to understand the actual dependency topology, not the assumed one. Set up trace-to-log correlation from day one — it's trivial to configure and invaluable during incident investigation. → `engineering-knowledge-repository/apm.md`

## Related Entries
- [Distributed Tracing](distributed-tracing.md) — APM is built on distributed tracing; APM tools add auto-instrumentation, UI, and analysis on top
- [Metrics and Alerting](metrics-and-alerting.md) — APM provides the application-layer metrics that complement infrastructure metrics
- [OpenTelemetry](opentelemetry.md) — OpenTelemetry provides the vendor-neutral instrumentation layer that APM tools consume
- [Real User Monitoring](real-user-monitoring.md) — RUM covers the frontend layer; APM covers the backend — together they give end-to-end visibility
- [Structured Logging](structured-logging.md) — APM trace ID injection into structured logs enables trace-to-log correlation

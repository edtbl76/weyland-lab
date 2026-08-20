---
id: api-observability
tags: [pattern, api-design, observability, backend]
surfaces-at: [nfr-requirements, application-design]
related: [openapi-specification, api-gateway-design, distributed-tracing, structured-logging, metrics-and-alerting]
complexity: intermediate
---

# API Observability

## What It Is
The instrumentation and tooling that provides visibility into API behavior in production — what requests are being made, how long they take, where they fail, and why. API observability combines structured access logging, metrics (latency, throughput, error rates), and distributed tracing into a coherent picture of API health. Without it, debugging production API failures is guesswork. With it, you can detect anomalies, diagnose root causes, and understand client usage patterns.

## When to Apply
- Every API exposed to clients — internal or external
- Before deploying to production — observability must be designed in, not added after incidents
- When SLAs or SLOs exist for API performance or availability

## Key Concepts
- **Structured Access Logs**: Log every request with structured fields — timestamp, method, path, status code, latency, client ID, request ID, user agent, response size. JSON format enables querying and alerting. Never log request/response bodies containing PII or credentials
- **Request ID / Correlation ID**: Assign a unique ID to every inbound request. Propagate it through all downstream service calls as a header (`X-Request-ID`, `X-Correlation-ID`). Enables tracing a single request across logs from multiple services
- **The Four Golden Signals** (applied to APIs):
  - *Latency*: p50, p95, p99 response times — percentiles matter more than averages
  - *Traffic*: Requests per second, broken down by endpoint and client
  - *Errors*: 4xx and 5xx error rates by endpoint and error type
  - *Saturation*: Queue depth, thread pool utilization, connection pool usage
- **Distributed Tracing**: Trace a request's path through the full system — API gateway → service → database → downstream services. OpenTelemetry is the standard instrumentation; Jaeger, Datadog, and AWS X-Ray are backends. Essential for microservice architectures
- **API Metrics**: Track per-endpoint: request count, error rate, latency percentiles. Instrument at the framework level (middleware) so every endpoint is covered without per-handler instrumentation. Prometheus + Grafana or Datadog APM
- **Alerting**: Alert on SLO violations — error rate > threshold, p99 latency > threshold. Alert on sudden traffic drops (may indicate client errors, not server errors). Route alerts to the owning team
- **API Analytics**: Understand client usage patterns — which endpoints are most used, which clients generate the most traffic, which endpoints have the highest error rates. Useful for deprecation decisions and capacity planning
- **Error Budget Tracking**: If you have SLOs, track error budget burn rate. A fast burn rate on an API endpoint indicates a reliability problem before the SLO is violated

## In Practice
Method APIs use OpenTelemetry for instrumentation. Structured JSON access logs go to CloudWatch Logs. Prometheus metrics (request count, latency histograms, error rates) are scraped and visualized in Grafana. Correlation IDs are generated at the API gateway and propagated through all service calls. Alerts fire on error rate > 1% or p99 > 2x baseline sustained for 5 minutes.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — API Observability**: Assign and propagate a correlation ID on every request — it's the single most valuable debugging tool when an incident spans multiple services. Log structured JSON access logs; never log PII or credentials. Track the four golden signals per endpoint: latency (percentiles), traffic, errors, saturation. Alert on SLO violations, not individual errors — one 500 isn't an incident, a sustained 2% error rate is. Use distributed tracing (OpenTelemetry) from day one in microservice architectures — adding it after the fact is painful. → `engineering-knowledge-repository/api-observability.md`

## Related Entries
- [OpenAPI Specification](openapi-specification.md) — API contracts inform what endpoints and behaviors to instrument
- [API Gateway Design](api-gateway-design.md) — API gateways are a natural instrumentation point for cross-cutting observability
- [Distributed Tracing](distributed-tracing.md) — tracing follows requests across service boundaries
- [Structured Logging](structured-logging.md) — structured logs are the foundation of API access log analysis
- [Metrics and Alerting](metrics-and-alerting.md) — API metrics feed into broader system monitoring and alerting

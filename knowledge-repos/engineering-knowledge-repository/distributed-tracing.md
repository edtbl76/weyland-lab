---
id: distributed-tracing
tags: [pattern, observability, distributed-systems]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [structured-logging, opentelemetry, correlation-ids, service-mesh, golden-signals]
complexity: intermediate
---

# Distributed Tracing

## What It Is
An observability technique that tracks a request's path through multiple services in a distributed system. Each service that processes the request records a **span** (operation name, start time, duration, metadata); spans are linked by a shared **trace ID** propagated in request headers. The complete set of spans forms a **trace** — a visual timeline showing where time was spent and where failures occurred across the full call chain.

## When to Apply
- Any microservices system where debugging a user-visible problem requires understanding which service is responsible
- Identifying latency bottlenecks across service boundaries
- Understanding the full call graph of a business transaction that spans multiple services
- Production debugging of intermittent failures that only reproduce with specific service interaction patterns

## When Not to Apply
- Single-service applications — standard logging and metrics are sufficient
- Systems without adequate sampling strategy — 100% trace capture at high throughput is expensive; configure sampling thoughtfully
- When the team lacks the infrastructure to store and query traces — a trace collector (Jaeger, Zipkin, Tempo) must be deployed and maintained

## Key Concepts
- **Trace**: A complete record of a single request's journey through the system — the forest of spans
- **Span**: A unit of work within a trace — name, service, start/end timestamps, status, and optional attributes
- **Trace ID**: A globally unique ID generated at the edge and propagated through all downstream calls — the thread connecting all spans
- **Parent Span / Child Span**: Spans form a tree — the parent span represents the caller; child spans represent downstream calls
- **W3C TraceContext**: The standard HTTP header format for propagating trace context (`traceparent`, `tracestate`)
- **Sampling**: Collecting every trace at high throughput is expensive — tail-based sampling (capture only slow or error traces) is the common production strategy
- **Tools**: Jaeger, Zipkin (open source); AWS X-Ray, Datadog APM, Honeycomb (managed)
- **OpenTelemetry**: The vendor-neutral instrumentation standard — instrument once, export to any backend

## In Practice
Distributed tracing is a standard observability requirement for Method microservices engagements. OpenTelemetry is the instrumentation standard — SDKs for all major languages automatically instrument HTTP, database, and messaging calls. The backend (Jaeger or a managed solution like Datadog/Honeycomb) must be chosen and deployed in Iteration 0. Auto-instrumentation reduces developer friction to near zero.

## Engineering Knowledge
💡 **Engineering Knowledge — Distributed Tracing**: When a user reports slowness and you have 10 services, distributed tracing tells you exactly which service is the bottleneck and why. Each service adds a span to the trace; all spans share a trace ID propagated in headers. Use OpenTelemetry for instrumentation — vendor-neutral, auto-instruments HTTP and DB calls. Deploy Jaeger or use a managed APM tool. Set up sampling (not 100%): tail-based sampling captures only slow and error traces at production throughput. → `engineering-knowledge-repository/observability/distributed-tracing.md`

## Related Entries
- [Structured Logging](structured-logging.md) — include trace ID in logs to correlate traces with log events
- [Correlation IDs](correlation-ids.md) — trace ID is a form of correlation ID propagated across services
- [OpenTelemetry](opentelemetry.md) — the instrumentation standard for distributed tracing
- [Service Mesh](../architectural-styles/service-mesh.md) — service mesh sidecars can generate traces automatically without application instrumentation

---
id: correlation-ids
tags: [pattern, observability, distributed-systems, network]
surfaces-at: [nfr-requirements, code-generation]
related: [distributed-tracing, structured-logging, opentelemetry]
complexity: foundational
---

# Correlation IDs

## What It Is
A unique identifier generated at the entry point of a system (API gateway, first service) and propagated through all downstream service calls for a single user-facing request. Every log entry, metric, and trace for that request includes the correlation ID, allowing all activity to be correlated across services during debugging. Also called a Request ID or Trace ID (the trace ID in distributed tracing systems serves the same purpose).

## When to Apply
- All microservices and distributed systems — correlation IDs are a minimal traceability requirement
- Any system where a user-visible operation touches more than one component
- As the foundation before implementing full distributed tracing — even if you can't implement tracing today, correlation IDs in logs are immediately valuable

## When Not to Apply
- Single-service applications where a single log line is sufficient to diagnose any request

## Key Concepts
- **Generation**: Created at the entry point — API gateway, front-door service, or client — before any processing occurs
- **Propagation**: Passed in HTTP headers (e.g., `X-Correlation-ID`, `X-Request-ID`) to all downstream service calls; included in message headers for async systems
- **Logging**: Every log statement for a request includes the correlation ID as a structured field
- **UUID v4**: The standard format — 128-bit random ID, low collision probability, globally unique
- **W3C TraceContext**: The distributed tracing standard (`traceparent` header) is the standardized form of correlation ID propagation — use this when implementing OpenTelemetry
- **User-Facing Errors**: Return the correlation ID in error responses — support teams can look it up in logs to trace exactly what failed

## In Practice
Correlation IDs are the simplest form of distributed traceability. Before OpenTelemetry is implemented, correlation IDs in structured logs give immediate debugging capability. The implementation is straightforward: middleware at the entry point generates or accepts an ID; it's stored in a request-scoped context (Thread Local, AsyncLocalStorage, Go's context.Context) and retrieved when logging. Return it in error responses — it's invaluable for support ticket debugging.

## Engineering Knowledge
💡 **Engineering Knowledge — Correlation IDs**: Generate a UUID at the entry point; propagate it in `X-Correlation-ID` headers to all downstream calls; include it in every log entry. When a user reports a bug, look up their request's correlation ID and get the complete picture across every service instantly. It's the simplest traceability investment you can make. Return the ID in error responses too — support teams will thank you. When you add distributed tracing, the trace ID takes over this role. → `engineering-knowledge-repository/observability/correlation-ids.md`

## Related Entries
- [Distributed Tracing](distributed-tracing.md) — trace ID is the standardized form of correlation ID in full distributed tracing systems
- [Structured Logging](structured-logging.md) — correlation IDs are only queryable when logs are structured

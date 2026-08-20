---
id: opentelemetry
tags: [tooling, observability, protocol]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [distributed-tracing, structured-logging, metrics-and-alerting, service-mesh]
complexity: intermediate
---

# OpenTelemetry (OTel)

## What It Is
A vendor-neutral, open-source observability framework that provides a single, standardized way to instrument applications for traces, metrics, and logs. OpenTelemetry merges the OpenCensus and OpenTracing projects. Instrument your application once with OTel SDKs; export telemetry to any backend (Jaeger, Prometheus, Datadog, Honeycomb, AWS X-Ray) by swapping the exporter — no re-instrumentation required.

## When to Apply
- Any new production service — instrument with OTel from day one
- Avoiding vendor lock-in for observability tooling — OTel lets you change backends without changing application code
- Polyglot microservices — OTel provides consistent SDKs for Java, Python, Node.js, Go, .NET, Ruby, PHP
- When you want to add distributed tracing and structured metrics with minimal manual instrumentation

## When Not to Apply
- If the team is already deeply invested in a vendor-specific SDK and migration cost is high — OTel is the right new-project choice but a considered migration for existing systems
- Very simple single-service applications where OTel overhead isn't warranted

## Key Concepts
- **SDK**: Language-specific libraries for instrumenting applications — automatically instruments popular frameworks (HTTP servers, database clients, messaging)
- **API**: The contract between instrumented code and the SDK — applications call the API; the SDK provides the implementation
- **OTLP (OpenTelemetry Protocol)**: The standard wire protocol for exporting telemetry to collectors and backends
- **Collector**: An OTel Collector can receive, process (filter, batch, transform), and export telemetry to multiple destinations — acts as a telemetry pipeline
- **Auto-Instrumentation**: OTel agents automatically instrument popular frameworks without code changes — Java agent, Node.js auto-instrumentation
- **Signals**: OTel supports three signals: Traces (request path), Metrics (numeric time-series), Logs (log records with trace correlation). Unified under one framework.

## In Practice
OpenTelemetry is Method's standard instrumentation framework for all new production services. Java services use the OTel Java agent (zero-code auto-instrumentation); Node.js services use `@opentelemetry/auto-instrumentations-node`; Python uses `opentelemetry-instrumentation`. The OTel Collector is deployed as infrastructure to aggregate and route telemetry. Backend choice (Jaeger, Honeycomb, Datadog) is independent of instrumentation.

## Engineering Knowledge
💡 **Engineering Knowledge — OpenTelemetry**: Instrument once, change backends freely. OTel is the standard for traces, metrics, and logs — SDKs for all major languages, auto-instrumentation for popular frameworks. Drop in the Java agent or Node.js auto-instrumentation and get distributed traces with no code changes. Use the OTel Collector to route telemetry to your chosen backend. Switching from Jaeger to Honeycomb tomorrow? Change the collector config, not your application code. → `engineering-knowledge-repository/observability/opentelemetry.md`

## Related Entries
- [Distributed Tracing](distributed-tracing.md) — OTel is the instrumentation layer for distributed traces
- [Metrics and Alerting](metrics-and-alerting.md) — OTel metrics complement traces and logs in the full observability picture
- [Structured Logging](structured-logging.md) — OTel log correlation attaches trace IDs to log records automatically

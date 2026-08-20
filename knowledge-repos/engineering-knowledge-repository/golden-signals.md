---
id: golden-signals
tags: [reference, observability]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [service-level-objectives, metrics-and-alerting, distributed-tracing, opentelemetry]
complexity: foundational
---

# Golden Signals

## What It Is
Four metrics identified in the Google SRE book as the most important signals for monitoring any user-facing service: **Latency**, **Traffic**, **Errors**, and **Saturation**. If you can only instrument four things, instrument these. Together, they provide a complete picture of service health and are the foundation for SLO definitions.

## When to Apply
- Instrumenting any production service — start here before adding more specific metrics
- Defining what to alert on — golden signal breaches are almost always worth alerting
- Defining SLIs for SLOs — latency and error rate are the most common SLI choices
- When reviewing observability gaps — if you can't measure any of the four signals, that's the gap to close first

## When Not to Apply
- The four signals are a starting point, not a ceiling — add application-specific business metrics once golden signals are covered

## Key Concepts
- **Latency**: The time to process a request. Measure the distribution (p50, p95, p99) — not just the average. Distinguish latency of successful requests from failed ones — high latency on errors may mask fast success paths.
- **Traffic**: The volume of demand on the system — requests per second, messages per second, active connections. Context for interpreting errors and latency.
- **Errors**: The rate of failed requests — HTTP 5xx, timeouts, exceptions. Distinguish explicit errors (5xx) from implicit ones (200 with wrong content).
- **Saturation**: How "full" the service is — CPU, memory, I/O utilization, queue depth. Saturation predicts upcoming latency increases before users notice them.
- **USE Method**: A complementary framework (Brendan Gregg) for infrastructure resources: Utilization, Saturation, Errors — per resource.
- **RED Method**: A variation for services: Rate (traffic), Errors, Duration (latency) — slightly simpler than the four golden signals.

## In Practice
Golden signals are the baseline observability standard in Method infrastructure engagements. Dashboard template: latency p99 + p50, error rate, RPS, CPU/memory saturation. Alerts: p99 latency SLO burn, error rate SLO burn, and saturation approaching capacity. OpenTelemetry auto-instrumentation generates traffic, latency, and error metrics automatically for HTTP services.

## Engineering Knowledge
💡 **Engineering Knowledge — Golden Signals**: If you instrument nothing else, instrument these four: Latency (p99, not average), Traffic (RPS), Errors (rate of failures), Saturation (how full is it). Together they tell you what's wrong, how bad it is, and why. Build your first dashboard and first SLOs from these. Saturation is the early warning signal — it degrades before users notice. OTel auto-instruments all four for HTTP services. → `engineering-knowledge-repository/observability/golden-signals.md`

## Related Entries
- [Service Level Objectives](service-level-objectives.md) — latency and error rate golden signals become SLIs for SLOs
- [Metrics and Alerting](metrics-and-alerting.md) — golden signals are the core set of metrics to alert on
- [OpenTelemetry](opentelemetry.md) — OTel generates golden signal metrics automatically for instrumented services

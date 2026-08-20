---
id: observability-cost-management
tags: [methodology, cost, observability, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [cloud-cost-optimization, finops, structured-logging, distributed-tracing, metrics-and-alerting, opentelemetry]
complexity: intermediate
---

# Observability Cost Management

## What It Is
Strategies for controlling the cost of logging, metrics, and distributed tracing infrastructure without sacrificing the visibility needed to operate production systems. Observability costs are frequently underestimated and can grow faster than the application they instrument — at scale, Datadog, Splunk, or CloudWatch bills routinely exceed database costs. The key levers are sampling (collect a representative fraction), cardinality control (limit high-cardinality dimensions), and retention policies (keep data only as long as needed).

## When to Apply
- When observability costs are a significant or growing line item
- Before onboarding a new observability platform — design sampling and retention upfront
- When evaluating observability tooling — cost structure varies dramatically between vendors
- As application scale grows and log/metric/trace volume increases proportionally

## Key Concepts
- **Log Sampling**: Not every log line needs to be stored. For high-volume INFO logs, sample a percentage (1-10%) rather than storing all. Always store ERROR and WARN logs in full. Structured sampling by log level dramatically reduces volume without losing signal
- **Metrics Cardinality**: High-cardinality dimensions (user_id, request_id, session_id as metric labels) create a unique time series per value — Prometheus and Datadog charge per time series. Use high-cardinality values only in logs and traces, not metric labels. Audit metrics cardinality regularly
- **Trace Sampling**: Storing every trace is expensive and redundant for healthy requests. Head-based sampling (decide at trace start — e.g., sample 10% of requests) reduces volume uniformly. Tail-based sampling (decide after the trace completes — keep 100% of error traces, sample successes) preserves signal while reducing cost. Prefer tail-based for production
- **Log Retention Tiers**: Hot storage (full-text search, recent logs — expensive) → warm storage (compressed, queryable, 30-90 days) → cold storage (archived to S3, query via Athena, 1+ years). Match retention tier to query frequency. Most logs are never queried after 7 days
- **Datadog / Splunk Cost Levers**: Log ingestion pricing — filter low-value logs at the agent before sending. Metrics custom metrics pricing — audit and remove unused metrics. APM pricing — adjust trace sample rate. Use log pipelines to drop or transform verbose logs before ingestion
- **OpenTelemetry Collector**: Process telemetry data before sending to the backend. Filter, sample, and transform at the collector layer — vendor-agnostic and free. Reduces backend ingestion costs without changing application instrumentation
- **Self-Hosted vs. Managed**: Managed platforms (Datadog, New Relic, Splunk) are expensive at scale but operationally simple. Self-hosted (Prometheus + Grafana + Loki + Jaeger) has lower unit costs but significant operational overhead. Hybrid: self-hosted for high-volume data, managed for dashboards and alerting
- **Alerts on Observability Costs**: Set budget alerts on observability spend — cost spikes from a runaway metric or log source are common and should be caught quickly

## In Practice
Method uses the OpenTelemetry Collector to filter and sample telemetry before sending to backends. Trace sampling is tail-based at 100% for errors, 5% for successful requests. Log retention is 30 days hot, 1 year cold (S3). Custom metric cardinality is reviewed in architecture reviews. Datadog cost is tracked per team in the FinOps dashboard.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Observability Cost Management**: Observability costs grow with scale and will surprise you if unmanaged. Cardinality is the primary metrics cost driver — never use user_id or request_id as metric labels. Use tail-based trace sampling: keep 100% of error traces, sample successes. Filter low-value logs at the OpenTelemetry Collector before they reach your paid backend — it's vendor-agnostic and reduces ingestion costs without changing instrumentation. Set log retention tiers — hot storage for recent logs, cold S3 for archives. Budget alerts on observability spend are as important as alerts on compute spend. → `engineering-knowledge-repository/observability-cost-management.md`

## Related Entries
- [Cloud Cost Optimization](cloud-cost-optimization.md) — observability cost is a significant component of total cloud spend
- [FinOps](finops.md) — observability costs should be attributed per team in the FinOps framework
- [Structured Logging](structured-logging.md) — structured logs enable precise filtering to reduce log volume before storage
- [Distributed Tracing](distributed-tracing.md) — trace sampling is the primary cost lever for distributed tracing infrastructure
- [Metrics and Alerting](metrics-and-alerting.md) — metrics cardinality management is critical to controlling metrics platform costs
- [OpenTelemetry](opentelemetry.md) — the OpenTelemetry Collector is the processing layer for cost-aware telemetry pipelines

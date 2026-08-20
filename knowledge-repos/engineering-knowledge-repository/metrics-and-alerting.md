---
id: metrics-and-alerting
tags: [tooling, observability]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [golden-signals, service-level-objectives, opentelemetry, distributed-tracing, alerting-fatigue]
complexity: intermediate
---

# Metrics and Alerting

## What It Is
Metrics are numeric, time-series measurements of system behavior — request rates, latency percentiles, error counts, CPU usage, queue depths. Alerting is the mechanism that triggers notifications when metrics breach defined thresholds. Together, they form the real-time operational awareness layer. The standard open-source stack: Prometheus (collection and storage), Grafana (dashboards), Alertmanager (alert routing).

## When to Apply
- All production systems — metrics and alerting are non-negotiable baseline observability
- SLO monitoring — SLIs are implemented as metrics; SLO burn rate alerts fire when error budgets are consumed too fast
- Capacity planning — saturation metrics predict when infrastructure must be scaled
- Performance regression detection — track p99 latency across deployments

## When Not to Apply
- Development and test environments — alerting only on production
- Excessive metric cardinality — defining metrics with unbounded label values (e.g., user_id as a label) causes storage explosion

## Key Concepts
- **Counter**: A cumulative, monotonically increasing value — request counts, error counts. Never decreases.
- **Gauge**: A value that can go up and down — current connections, memory usage, queue depth
- **Histogram**: Distributes observations into configurable buckets — used for latency percentiles (p50, p95, p99)
- **Cardinality**: The number of unique label combinations — high cardinality (e.g., one series per user) causes metric storage to explode
- **Scraping**: Prometheus pulls metrics from instrumented services on a polling interval — services expose a `/metrics` endpoint
- **Push Gateway**: For batch jobs that don't live long enough to be scraped — push metrics to the gateway
- **Alert Rules**: Prometheus AlertManager rules define conditions and routing — alert on SLO burn rate, not raw thresholds
- **Runbook Links**: Every alert should link to a runbook that tells on-call what to do — alerts without runbooks cause hesitation

## In Practice
Prometheus + Grafana is Method's standard metrics stack for Kubernetes deployments. Prometheus Operator simplifies setup in Kubernetes. Managed alternatives (Datadog, New Relic, AWS CloudWatch) reduce operational overhead. Alert routing to PagerDuty or OpsGenie with priority levels (P1 = wake someone up; P3 = business hours ticket). Alert on SLO burn rate, not raw error counts — burn rate alerting is more actionable and less noisy.

## Engineering Knowledge
💡 **Engineering Knowledge — Metrics and Alerting**: Prometheus + Grafana is the standard stack: services expose `/metrics`, Prometheus scrapes and stores, Grafana visualizes. Use histograms for latency (you need percentiles, not averages). Alert on SLO burn rate — "the error budget is burning 14x faster than normal" is more actionable than "5 errors in the last minute." Every alert must link to a runbook. High cardinality (user IDs as metric labels) will blow up your metric storage — keep label cardinality bounded. → `engineering-knowledge-repository/observability/metrics-and-alerting.md`

## Related Entries
- [Golden Signals](golden-signals.md) — the four core metrics to instrument and alert on
- [Service Level Objectives](service-level-objectives.md) — alert on SLO burn rate derived from metrics
- [Alerting Fatigue](alerting-fatigue.md) — the anti-pattern that results from too many low-quality alerts
- [OpenTelemetry](opentelemetry.md) — OTel generates metrics that are exported to Prometheus

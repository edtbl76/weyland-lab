---
id: log-aggregation
tags: [pattern, observability, infrastructure]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [structured-logging, distributed-tracing, correlation-ids, sidecar-pattern]
complexity: intermediate
---

# Log Aggregation

## What It Is
The practice of collecting logs from all services and infrastructure into a single, searchable central store. In distributed systems, logs are scattered across dozens of containers and instances — without aggregation, debugging requires SSH-ing to individual machines. Centralized log aggregation makes the entire system's activity queryable in one place. Common stacks: ELK (Elasticsearch, Logstash, Kibana), Grafana Loki + Grafana, Splunk, Datadog Logs, AWS CloudWatch Logs.

## When to Apply
- Any distributed system with more than one service — single-machine log access doesn't scale
- When debugging requires correlating events across multiple services (with correlation IDs)
- Compliance requirements for log retention and audit trail
- When ephemeral containers lose logs on termination — aggregate before they disappear

## When Not to Apply
- Single-instance applications where local log access is sufficient
- Very cost-constrained environments where full ELK stack overhead isn't justified (use Loki instead — it's significantly cheaper for log storage)

## Key Concepts
- **Log Shipping**: Getting logs from the source to the aggregator. Common approaches: sidecar agent (Filebeat in a sidecar container), node-level agent (DaemonSet), direct SDK shipping (Fluent Bit)
- **ELK Stack**: Elasticsearch (storage/search) + Logstash (ingestion/transformation) + Kibana (visualization). Powerful but resource-intensive.
- **Grafana Loki**: Log aggregation designed for cost efficiency — stores only indexes and pointers; retrieves log content from object storage (S3). Dramatically cheaper than Elasticsearch for log-heavy workloads.
- **Retention Policy**: Define how long logs are kept — typically 30 days hot, 90 days archived. Balance debugging needs with storage cost.
- **Index by Service and Environment**: Separate indexes or streams per service and environment — prevents production logs from being polluted by test traffic
- **Log Volume Management**: Debug-level logging in production can produce enormous volumes. Log level configuration per environment is essential.

## In Practice
For Kubernetes-based Method engagements, Grafana Loki (with Promtail for collection) is the cost-effective standard recommendation. For clients with compliance requirements or complex log analysis needs, ELK or Splunk is justified. Filebeat/Fluent Bit sidecar or DaemonSet log collection is configured in Iteration 0 alongside the rest of the observability stack.

## Engineering Knowledge
💡 **Engineering Knowledge — Log Aggregation**: Containers die; logs disappear. Aggregate logs centrally before they're gone. For Kubernetes workloads, Grafana Loki is cost-effective (cheap S3 storage vs. Elasticsearch's indexing overhead). ELK is more powerful for complex queries but expensive. Include correlation IDs in structured logs so you can filter all logs for one request across every service. Set retention policies — 30 days hot, 90 days archived is a common starting point. → `engineering-knowledge-repository/observability/log-aggregation.md`

## Related Entries
- [Structured Logging](structured-logging.md) — structured logs are what make aggregated logs queryable
- [Sidecar Pattern](../infrastructure/sidecar-pattern.md) — log shipping agents are frequently deployed as sidecars
- [Correlation IDs](correlation-ids.md) — correlation IDs are the primary cross-service query field in aggregated logs

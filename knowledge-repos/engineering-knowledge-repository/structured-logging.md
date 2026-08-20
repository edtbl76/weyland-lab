---
id: structured-logging
tags: [pattern, observability, backend]
surfaces-at: [nfr-requirements, code-generation]
related: [distributed-tracing, log-aggregation, correlation-ids, opentelemetry, audit-logging]
complexity: foundational
---

# Structured Logging

## What It Is
An approach to logging where log entries are written as machine-parseable key-value records (typically JSON) rather than free-form text strings. Instead of `"User 12345 logged in at 14:32:00"`, a structured log entry is `{"event":"user_login","user_id":12345,"timestamp":"2026-04-16T14:32:00Z","duration_ms":45}`. Structured logs can be queried, filtered, and aggregated by any field — unstructured logs can only be searched by text pattern.

## When to Apply
- All production systems — structured logging is a baseline practice, not an optimization
- Systems that aggregate logs centrally (ELK stack, Splunk, Datadog, CloudWatch) — structured logs are dramatically more queryable than unstructured
- Any application where you need to filter by user ID, request ID, error type, or any other dimension
- Services that must correlate logs with distributed traces (include trace ID as a log field)

## When Not to Apply
- Simple local scripts and development tools where human-readable text output is more useful
- Systems with extremely high log volume where JSON serialization overhead is a measurable concern (profile first)

## Key Concepts
- **JSON Log Format**: Each log entry is a JSON object — structured fields are first-class, not buried in a message string
- **Log Levels**: ERROR, WARN, INFO, DEBUG — use consistently; don't log INFO in production code paths that execute on every request
- **Mandatory Fields**: Every log entry should include: timestamp (ISO 8601), log level, service name, trace ID / request ID, and the specific event fields
- **Contextual Fields**: Add fields at logger initialization (service, version, environment) so they appear on every entry without repeating them
- **Cardinality**: High-cardinality fields (user IDs, request IDs) are queryable in structured logs — impossible in free-form text
- **Log Aggregator Integration**: Structured logs flow into ELK (Elasticsearch + Logstash + Kibana), Splunk, Datadog, or CloudWatch Logs Insights — all support JSON parsing and field-level queries

## In Practice
Structured logging is Method's baseline logging standard for all production services. SLF4J + Logback/Log4j2 with JSON encoder (Logstash encoder) for JVM; Pino or Winston for Node.js; Python's `structlog` for Python. Include the trace ID from the request context on every log entry — this connects distributed traces to log data during incident investigation.

## Engineering Knowledge
💡 **Engineering Knowledge — Structured Logging**: Log JSON, not strings. `{"event":"order_failed","order_id":"abc123","error":"payment_timeout","user_id":"u456"}` is queryable by any field; `"Order abc123 failed: payment timeout"` is only searchable as a text pattern. Add trace ID to every log entry — it connects your logs to your distributed traces. Use Pino (Node), structlog (Python), or Logstash JSON encoder (JVM). Every log entry needs: timestamp, level, service, trace ID, and event-specific fields. → `engineering-knowledge-repository/observability/structured-logging.md`

## Related Entries
- [Distributed Tracing](distributed-tracing.md) — include trace ID in structured logs to correlate with traces
- [Log Aggregation](log-aggregation.md) — structured logs are what make log aggregation systems queryable
- [Correlation IDs](correlation-ids.md) — trace ID / request ID is the key correlation field in structured logs

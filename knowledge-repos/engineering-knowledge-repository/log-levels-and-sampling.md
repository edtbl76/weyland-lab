---
id: log-levels-and-sampling
tags: [methodology, observability, backend]
surfaces-at: [application-design, functional-design]
related: [structured-logging, log-aggregation, observability-cost-management, distributed-tracing]
complexity: foundational
---

# Log Levels and Sampling

## What It Is
The conventions for categorizing log output by severity and the techniques for selectively capturing a representative subset of log events to balance observability with cost and performance. Getting log levels wrong (logging everything at DEBUG in production, or logging nothing useful at ERROR) makes log-based debugging ineffective. Logging too much drives observability costs up; logging too little leaves blind spots. Log sampling is the technique for high-volume services where logging every event would be prohibitively expensive but losing all visibility is unacceptable.

## When to Apply
- Every service that produces logs (all of them)
- When log storage costs are high and a significant portion of logs are never queried
- When log volume is impacting application performance
- When debugging production issues is consistently difficult due to insufficient log context

## Key Concepts
- **Standard Log Levels** (in ascending severity):
  - *TRACE*: Extremely verbose; individual function entry/exit, loop iterations. Never in production. Development-only
  - *DEBUG*: Detailed diagnostic information useful during development — variable values, state transitions, decision branches. Disabled in production by default; enable dynamically for targeted debugging
  - *INFO*: Normal operational events — service started, request received, significant business event completed (order placed, user authenticated). The baseline production log level. Should be meaningful, not chatty
  - *WARN*: Unexpected but handled conditions — fallback to default, retrying a failed operation, deprecated API usage, approaching a resource limit. Warrants attention but doesn't require immediate action
  - *ERROR*: Operation failed in a way that requires intervention or investigation — database connection failed, payment processing error, unhandled exception. Every ERROR should either trigger an alert or be triaged manually
  - *FATAL / CRITICAL*: Service cannot continue operating. Triggers immediate alerting; usually causes process termination
- **Log Level Decision Guide**:
  - Does this log entry describe expected normal behavior? → INFO
  - Does this describe something unexpected that was handled? → WARN
  - Did an operation fail and the user or system is affected? → ERROR
  - Is this only useful for debugging a specific problem? → DEBUG (disabled in prod)
  - Would this embarrass you if a customer read it in a data breach? → Don't log it
- **Dynamic Log Level Adjustment**: Configure log level at runtime without redeployment. Useful for temporarily increasing verbosity to DEBUG during a production investigation. Feature flag systems or environment variable reloads enable this
- **What NOT to Log**:
  - Passwords, secrets, API keys
  - PII (email, phone, SSN, credit card numbers) — or log only masked versions
  - Full request/response bodies containing sensitive data
  - Logs that are only ever "we got here" with no context — they add noise without value
- **Log Sampling**: For high-volume, low-value log events (health check endpoints, routine API calls), sample a fraction to reduce volume while preserving visibility:
  - *Rate-based sampling*: Log 1 in N events (1 in 100 health check requests). Simple; maintains statistical representation
  - *Head-based sampling*: Decision made at request start; all logs for a sampled request are captured
  - *Tail-based sampling*: Decision made after the request completes, biased toward errors and slow requests. Keeps all errors; samples away the successful fast requests. Most useful for trace sampling; more complex to implement for logs
- **Sampling in Practice**: Use sampling for INFO-level high-frequency events. Never sample WARN or ERROR — every warning and error should be captured
- **Correlation with Traces**: Log the trace ID and span ID with every log entry. This enables jumping from a Datadog trace to the associated log lines — the most important log enrichment for production debugging

## In Practice
Method services log at INFO level in production. DEBUG logs are disabled by default; toggled via LaunchDarkly flags for targeted production investigation. Health check endpoints (`/health`) are sampled at 1% — only 1 in 100 requests is logged. All WARN and ERROR logs are captured fully. Trace IDs are injected into all log entries via OpenTelemetry. PII fields are masked in the logging middleware before writing.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Log Levels and Sampling**: Logging everything at DEBUG in production is not "being thorough" — it's paying 10x for storage and making signal-to-noise unusable. INFO should describe meaningful events that tell the story of what the service did; DEBUG should describe what the code did internally. Never log PII or secrets — no log level makes that acceptable. Sample high-frequency low-value logs (health checks, routine requests) but never sample WARN or ERROR. Add trace ID to every log line from day one — the first time you need to correlate a trace to its logs during an incident, you'll be glad it's there. → `engineering-knowledge-repository/log-levels-and-sampling.md`

## Related Entries
- [Structured Logging](structured-logging.md) — log levels are part of the structured log schema; structured logging makes level-based filtering efficient
- [Log Aggregation](log-aggregation.md) — log aggregation systems filter, route, and store logs by level
- [Observability Cost Management](observability-cost-management.md) — log sampling is a primary lever for controlling log ingestion costs
- [Distributed Tracing](distributed-tracing.md) — trace ID injection into logs enables trace-to-log correlation

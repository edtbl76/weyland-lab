---
id: polling-consumer
tags: [pattern, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [idempotency, webhook-pattern, long-polling-sse-websockets, asynchronous-processing, rest-constraints]
complexity: intermediate
---

# Polling Consumer

## What It Is
A pattern for handling long-running or asynchronous API operations. Instead of holding an HTTP connection open while work completes (which times out for anything taking more than a few seconds), the server accepts the request, returns `202 Accepted` immediately with a reference to a status resource, and the client polls that resource until the operation reaches a terminal state. The pattern decouples request acceptance from result delivery.

## When to Apply
- Any API operation that takes more than a few seconds: report generation, bulk imports, ML inference jobs, video processing, complex calculations
- When the consumer cannot receive webhooks (firewall constraints, no public endpoint)
- Async job submission in batch processing systems

## When Not to Apply
- Fast operations (< 1 second) — synchronous response is simpler
- When the consumer can receive webhooks — webhooks are more efficient (no polling overhead)
- Real-time streaming use cases — use SSE or WebSockets instead

## Key Concepts
- **`202 Accepted`**: The correct HTTP status code for "I've received your request and will process it." The response body contains a job/task resource or a `Location` header pointing to the status endpoint
- **`Location` Header**: `Location: /jobs/abc123` — points to the resource the client should poll for status
- **Status Resource**: A resource at a stable URL representing the job state:
  ```json
  {
    "id": "abc123",
    "status": "processing",  // pending | processing | completed | failed
    "progress": 45,
    "created_at": "...",
    "completed_at": null,
    "result_url": null
  }
  ```
- **Terminal States**: `completed` and `failed` are terminal — the client stops polling. Non-terminal: `pending`, `processing`
- **`Retry-After` Header**: Include on status responses to tell the client how long to wait before polling again — prevents thundering herd and unnecessary requests
- **Result Retrieval**: On completion, either include the result in the status resource or provide a `result_url` pointing to the result resource (useful for large results)
- **Expiry**: Job resources should expire after a reasonable period (24-72 hours) — clients that poll indefinitely are a resource leak
- **Idempotency**: The initial `POST` submission should support an `Idempotency-Key` — duplicate submissions return the existing job rather than creating a new one

## In Practice
Method async operations return `202 Accepted` with a `Location: /jobs/{id}` header. The job resource exposes `status`, `progress`, and `result_url` on completion. `Retry-After: 5` is returned on in-progress polls. Jobs expire after 24 hours. Idempotency keys are supported on submission.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Polling Consumer**: For operations that take more than a few seconds, don't hold the connection open — return `202 Accepted` + `Location: /jobs/{id}` immediately. Client polls the status resource until `completed` or `failed`. Include `Retry-After` on polling responses to guide interval. Provide a `result_url` for large results. Add idempotency key support on submission. Expire jobs after 24-72 hours. If the consumer can receive webhooks, send a webhook on completion instead — polling is the fallback when webhooks aren't feasible. → `engineering-knowledge-repository/api-design/polling-consumer.md`

## Related Entries
- [Idempotency](idempotency.md) — job submission endpoints need idempotency keys
- [Webhook Pattern](webhook-pattern.md) — webhooks are the preferred alternative to polling for async job completion
- [Long Polling, SSE, and WebSockets](long-polling-sse-websockets.md) — alternatives for real-time update delivery
- [Asynchronous Processing](../performance/asynchronous-processing.md) — the backend pattern that polling consumer exposes via API

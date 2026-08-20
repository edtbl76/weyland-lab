---
id: async-request-response
tags: [pattern, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [polling-consumer, webhook-pattern, long-polling-sse-websockets, idempotency, error-response-standards]
complexity: intermediate
---

# Async Request-Response Pattern

## What It Is
An API pattern for handling long-running operations where the work cannot complete within a single HTTP request-response cycle. The client submits a request, receives an immediate 202 Accepted response with a job reference, and then checks status either by polling a status endpoint or receiving a callback when complete. This pattern prevents HTTP timeouts, enables horizontal scaling of work processing, and gives clients visibility into operation progress.

## When to Apply
- Operations that take more than a few seconds (report generation, batch processing, ML inference, file processing, data exports)
- Work that must be queued and processed asynchronously by workers
- Operations where progress feedback is valuable to the client
- Any operation where a synchronous response would require holding an HTTP connection open beyond timeout thresholds

## Key Concepts
- **202 Accepted**: The HTTP status code for "request accepted for processing, not yet complete." Must include a `Location` header pointing to the status resource, or a job ID in the response body
- **Status Resource**: A dedicated endpoint (`GET /jobs/{id}`) that returns the current state of the async operation: pending, processing, complete, failed. Include progress percentage when available
- **Status States**: `pending` (queued), `processing` (in progress), `complete` (success — include result or result location), `failed` (include error detail)
- **Polling Strategy**: Client polls the status endpoint at intervals. Include a `Retry-After` header on 202 responses to guide polling frequency. Exponential backoff prevents thundering herd on popular operations
- **Callback / Webhook Completion**: Instead of polling, the API notifies the client via webhook when the operation completes. More efficient for long operations; requires the client to expose a callback URL
- **Result Retrieval**: On completion, the status resource either contains the result inline (small results) or provides a link to retrieve the result (`GET /jobs/{id}/result`). For large results, use a pre-signed URL to object storage
- **Job TTL**: Status and result resources should have a defined retention period. Communicate expiry in the response. Clean up expired jobs to prevent unbounded storage growth
- **Idempotency**: Job submission should be idempotent — submitting the same request twice should return the existing job, not create a duplicate. Use a client-provided idempotency key

## In Practice
Method implements async operations with a jobs table, a worker queue (SQS), and a `GET /jobs/{id}` status endpoint. 202 responses include the job ID and a `Location` header. `Retry-After` is set to a reasonable polling interval based on expected operation duration. Webhook callbacks are offered as an alternative to polling for clients that support them.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Async Request-Response**: Return 202 Accepted immediately for any operation that can't complete in a few seconds — never hold an HTTP connection open waiting for slow work. Always include a `Location` header or job ID so clients can check status. Provide a `Retry-After` hint to prevent clients from hammering the status endpoint. Make job submission idempotent. Offer webhook callbacks as an alternative to polling for operations with long wait times. Define job TTL and communicate it — status endpoints aren't permanent. → `engineering-knowledge-repository/async-request-response.md`

## Related Entries
- [Polling Consumer](polling-consumer.md) — client-side polling pattern for checking async operation status
- [Webhook Pattern](webhook-pattern.md) — callback alternative to polling for async operation completion
- [Long Polling, SSE, WebSockets](long-polling-sse-websockets.md) — real-time push alternatives for status updates
- [Idempotency](idempotency.md) — async job submission must be idempotent to prevent duplicate work
- [Error Response Standards](error-response-standards.md) — failed async jobs must return structured error detail on the status endpoint

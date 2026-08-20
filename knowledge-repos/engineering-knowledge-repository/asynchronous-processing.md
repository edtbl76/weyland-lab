---
id: asynchronous-processing
tags: [pattern, performance, backend]
surfaces-at: [functional-design, nfr-requirements, application-design]
related: [event-driven-architecture, dead-letter-queue, caching-strategies, horizontal-vs-vertical-scaling]
complexity: intermediate
---

# Asynchronous Processing

## What It Is
The practice of deferring time-consuming operations to background workers so that the initial request can respond immediately, rather than making the user wait for the full operation to complete. Instead of processing synchronously within the request, work is enqueued (to a message queue, job queue, or event stream) and processed by workers independently. The request returns a "job accepted" response; the client polls or receives a webhook when the job completes.

## When to Apply
- Operations that take more than a few hundred milliseconds to complete (image processing, document generation, email sending, data imports)
- Operations where the user doesn't need the result immediately
- Decoupling high-priority, user-facing operations from low-priority background work
- Rate-limited operations — queue work and process at a controlled rate

## When Not to Apply
- Operations where the user needs the result synchronously (a real-time search, a payment authorization)
- Very simple, fast operations where the overhead of queuing is greater than the processing time
- When eventual consistency is unacceptable for the use case

## Key Concepts
- **Job Queue**: A system (Sidekiq, BullMQ, Celery, AWS SQS + Lambda) that accepts jobs, persists them durably, and distributes them to workers
- **Worker**: A background process that consumes jobs from the queue and executes them
- **Idempotent Jobs**: Background jobs may be retried — design them to be safe to execute multiple times
- **Job Priority**: Critical jobs (user-facing consequences) can be assigned higher priority than background cleanup
- **Progress Reporting**: Long-running jobs should update progress status that the client can poll
- **Dead Letter Queue**: Where jobs go after all retries are exhausted — requires monitoring and remediation process
- **Webhook Callback**: Alternative to polling — the background job calls a webhook when complete

## In Practice
Asynchronous processing is a standard architecture decision in Method engagements for any operation taking more than 500ms. AWS SQS + Lambda is the serverless standard; Sidekiq (Ruby), Celery (Python), and BullMQ (Node.js) are standard for persistent worker fleets. The key design decisions: idempotency, retry policy, and dead letter queue handling.

## Engineering Knowledge
💡 **Engineering Knowledge — Asynchronous Processing**: Don't make users wait for slow operations. Enqueue the work, return immediately, process in the background. Image processing, email sending, PDF generation, data imports — all should be async. Design jobs to be idempotent (they'll be retried). Configure a DLQ for jobs that fail repeatedly. For long operations, provide a status endpoint so the client can poll for completion or configure a webhook callback. → `engineering-knowledge-repository/performance/asynchronous-processing.md`

## Related Entries
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — async processing is a natural fit for event-driven systems
- [Dead Letter Queue](../infrastructure/dead-letter-queue.md) — DLQ captures background jobs that fail all retries

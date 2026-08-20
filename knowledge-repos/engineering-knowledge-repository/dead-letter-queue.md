---
id: dead-letter-queue
tags: [pattern, reliability, distributed-systems, backend]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [retry-pattern, event-driven-architecture, saga-pattern, outbox-pattern]
complexity: foundational
---

# Dead Letter Queue (DLQ)

## What It Is
A message queue that holds messages that could not be successfully processed after all retry attempts are exhausted. When a consumer fails to process a message repeatedly, the message is moved to the DLQ rather than blocking the queue or being discarded. The DLQ enables operations teams to inspect failed messages, diagnose root causes, and replay or discard them manually or programmatically. Supported natively by AWS SQS, Azure Service Bus, RabbitMQ, and most enterprise message brokers.

## When to Apply
- Any system using message queues for asynchronous processing
- Event-driven pipelines where individual message failures should not block the stream
- Systems where failed message data has business value and must not be lost
- Production systems where operational visibility into processing failures is required

## When Not to Apply
- Synchronous request-response systems — DLQ is a messaging concept
- When message loss is explicitly acceptable and simplicity is preferred
- Extremely high-throughput streaming pipelines where DLQ processing latency is incompatible with requirements (consider poison pill detection instead)

## Key Concepts
- **Poison Pill**: A message that can never be successfully processed — causes the consumer to fail every time. The DLQ is the safety net for poison pills.
- **Max Receive Count**: The number of times a message is delivered before being moved to the DLQ. Configure this as part of queue setup.
- **DLQ Monitoring**: Alert on DLQ depth — messages in the DLQ indicate production failures requiring investigation. A non-empty DLQ is an ops signal.
- **Message Replay**: After diagnosing and fixing the root cause, messages in the DLQ can be replayed to the original queue. Replay requires idempotent consumers.
- **DLQ Per Queue**: Each queue should have its own dedicated DLQ — mixing failures from different queues makes diagnosis harder
- **Retention Period**: DLQ messages have a configured retention window. Set long enough to allow diagnosis and replay; DLQ is not permanent storage.

## In Practice
DLQ configuration is a standard part of Method's infrastructure design for any event-driven system. A DLQ without monitoring is half-value — always configure CloudWatch alarms (or equivalent) on DLQ depth so that failures surface to on-call. DLQ replay procedures should be documented and tested before production incidents occur. In saga implementations, a DLQ for saga step failures is the starting point for manual compensating transaction workflows.

## Engineering Knowledge
💡 **Engineering Knowledge — Dead Letter Queue**: When a message can't be processed, don't block the queue or silently discard it — move it to a DLQ. The DLQ is your safety net for poison pills and transient failures that outlasted your retry budget. Configure DLQ depth alerts — a silent DLQ is a dangerous DLQ. After fixing the root cause, replay the DLQ; make sure your consumers are idempotent before you do. → `engineering-knowledge-repository/infrastructure/dead-letter-queue.md`

## Related Entries
- [Retry Pattern](retry-pattern.md) — retries are exhausted before a message is sent to the DLQ
- [Event-Driven Architecture](../architectural-styles/event-driven-architecture.md) — DLQs are standard infrastructure for event-driven systems
- [Saga Pattern](saga-pattern.md) — DLQs capture failed saga steps requiring manual intervention
- [Outbox Pattern](outbox-pattern.md) — the outbox ensures messages reach the broker; the DLQ handles downstream consumer failures

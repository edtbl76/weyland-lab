---
id: webhook-pattern
tags: [pattern, api-design, backend, network]
surfaces-at: [application-design, functional-design]
related: [idempotency, api-security, long-polling-sse-websockets, polling-consumer, asynchronous-processing]
complexity: intermediate
---

# Webhook Pattern

## What It Is
An event-driven integration mechanism where a service notifies consumers of events by making HTTP POST requests to consumer-registered URLs. Instead of consumers polling for changes, the producer pushes events as they occur. Webhooks are the standard mechanism for integrating with third-party platforms (Stripe, GitHub, Twilio) and for building event-driven architectures across organizational boundaries where message queues are not shared.

## When to Apply
- Notifying external systems of events in near-real-time without requiring them to poll
- Third-party integration where the consumer cannot share your message broker
- Building platform APIs where consumers register for events (payment completed, order shipped)

## When Not to Apply
- Internal service-to-service communication within your own system — use a message broker instead
- When the consumer cannot expose a public HTTPS endpoint (firewall constraints)
- Very high-frequency events — webhooks carry per-event HTTP overhead; consider SSE or a message queue

## Key Concepts
- **Payload Signing**: Include an HMAC-SHA256 signature header (`X-Webhook-Signature`) computed over the request body using a shared secret. Consumers verify the signature before processing — prevents forged events
- **At-Least-Once Delivery**: Webhooks are delivered at-least-once — the producer retries on failure (non-2xx response, timeout). Consumers must be idempotent — duplicate events will arrive
- **Retry with Exponential Backoff**: On delivery failure, retry with exponential backoff (1s, 2s, 4s, 8s...) up to a maximum attempt count (e.g., 24 hours). After exhausting retries, dead-letter the event
- **Event Envelope**: Include a consistent event structure: `{ "id": "evt_123", "type": "order.completed", "created_at": "...", "data": {...} }`. The `id` enables idempotency; `type` enables routing
- **Delivery Log**: Maintain a log of webhook delivery attempts with status — consumers can query past deliveries for debugging. Stripe's webhook dashboard is the gold standard
- **Consumer Acknowledgment**: Consumers respond with `2xx` to acknowledge receipt. Processing should be asynchronous — acknowledge immediately, process in a background queue. Long-running processing causes timeouts and spurious retries
- **Secret Rotation**: Provide a mechanism for consumers to rotate their signing secret without downtime — support a brief overlap period where both old and new secrets are valid
- **Webhook Registration**: Consumers register URLs via API or UI. Support event type filtering — consumers subscribe only to event types they care about

## In Practice
Method webhook implementations include HMAC-SHA256 signing, retry with exponential backoff (max 72 hours), a delivery log accessible via API, and an event envelope with stable `id` and `type` fields. Consumer documentation prominently features idempotency requirements and signature verification. Background queue processing is required — no synchronous webhook processing.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Webhook Pattern**: Always sign payloads (HMAC-SHA256) — consumers must verify before processing. Deliver at-least-once with exponential backoff retry. Consumers must be idempotent — duplicates will happen. The consumer should acknowledge immediately (2xx) and process asynchronously — never do slow work inline or you'll cause timeout-triggered retries. Include a stable event `id` for idempotency keys. Provide a delivery log. Support event type filtering so consumers only receive what they need. → `engineering-knowledge-repository/api-design/webhook-pattern.md`

## Related Entries
- [Idempotency](idempotency.md) — webhook consumers must implement idempotent event processing
- [API Security](../security/api-security.md) — webhook signature verification is a security requirement
- [Polling Consumer](polling-consumer.md) — polling is the alternative when webhooks are not feasible
- [Asynchronous Processing](../performance/asynchronous-processing.md) — webhook consumers should process events asynchronously

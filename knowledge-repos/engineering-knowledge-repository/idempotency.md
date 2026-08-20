---
id: idempotency
tags: [principle, api-design, reliability, backend]
surfaces-at: [application-design, functional-design, nfr-requirements]
related: [rest-constraints, webhook-pattern, polling-consumer, asynchronous-processing]
complexity: intermediate
---

# Idempotency

## What It Is
An operation is idempotent if performing it multiple times produces the same result as performing it once. In HTTP: GET, PUT, and DELETE are idempotent by definition. POST and PATCH are not — but they can be made idempotent via an `Idempotency-Key` header. In distributed systems, retries are unavoidable (networks fail, timeouts occur) — idempotency ensures retries are safe. Without it, a retry of a payment or order creation can charge a customer twice.

## When to Apply
- Any POST or PATCH operation with significant side effects: payments, order creation, email sending, inventory reservation
- APIs consumed by mobile clients or systems that retry on network failure
- Async job submission endpoints
- Any operation where "did this succeed?" is ambiguous due to network timeout

## Key Concepts
- **`Idempotency-Key` Header**: A client-generated UUID included with the request. The server stores the key and the response. On retry with the same key, the server returns the stored response without re-executing the operation
- **Key Lifetime**: Idempotency keys should expire after a reasonable window (24 hours is common). Beyond that, the same key is treated as a new request
- **Storage**: Keys and responses are stored in a fast key-value store (Redis) with TTL. The key is scoped to the authenticated client — two clients can use the same UUID safely
- **Idempotency vs. At-Least-Once Delivery**: They are related but different. At-least-once delivery guarantees the message arrives; idempotency guarantees duplicate arrivals are harmless
- **HTTP Method Idempotency**: GET (safe + idempotent), PUT (idempotent — full replace), DELETE (idempotent — deleting an already-deleted resource returns 404, which is acceptable), POST (not idempotent by default), PATCH (not idempotent by default)
- **Natural Idempotency**: Some operations are naturally idempotent if designed correctly — `PUT /users/123/status { "active": true }` is idempotent; `POST /users/123/activate` may not be
- **Stripe's Model**: Stripe popularized the `Idempotency-Key` header — it is the de facto standard for payment APIs and is now broadly adopted

## In Practice
Method implements idempotency for all payment, order, and messaging endpoints using Redis-backed key storage with 24-hour TTL. The `Idempotency-Key` header is documented in OpenAPI as required for these operations. Clients (mobile apps, retry-capable HTTP clients) are expected to generate a UUID per logical operation and reuse it on retry.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Idempotency**: Retries are inevitable — networks fail, clients timeout. Make POST/PATCH operations safe to retry with an `Idempotency-Key` header. Server stores key + response in Redis with 24h TTL; on duplicate key, returns stored response without re-executing. Critical for payments, order creation, and any operation with irreversible side effects. Design PUT operations to be naturally idempotent (full replace semantics). Stripe's model is the standard to follow. → `engineering-knowledge-repository/api-design/idempotency.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — HTTP method idempotency semantics
- [Webhook Pattern](webhook-pattern.md) — webhook consumers must be idempotent; events are delivered at-least-once
- [Polling Consumer](polling-consumer.md) — async job submission endpoints benefit from idempotency keys
- [Asynchronous Processing](../performance/asynchronous-processing.md) — background jobs must handle duplicate delivery idempotently

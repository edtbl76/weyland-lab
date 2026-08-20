---
id: bulk-batch-operations
tags: [pattern, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, idempotency, pagination-patterns, asynchronous-processing]
complexity: intermediate
---

# Bulk / Batch Operations

## What It Is
API endpoints designed to create, update, or delete multiple resources in a single request. Rather than requiring clients to issue N individual requests (with N round trips, N authentication checks, and N units of overhead), bulk endpoints accept an array of operations and process them together. Well-designed bulk endpoints return per-item results, support partial success, and are idempotent.

## When to Apply
- Importing or seeding data where clients need to create many records
- ETL and integration scenarios where external systems push batches of events or records
- Mobile clients with unreliable connectivity that need to sync accumulated operations
- Any scenario where N sequential requests would cause unacceptable latency or rate limit exhaustion

## When Not to Apply
- When individual operations have independent side effects that must be visible between calls
- Very large datasets (thousands of records) — consider async batch processing instead of synchronous bulk endpoints

## Key Concepts
- **Endpoint Design**: `POST /resources/batch` with a body containing an array of operations. Alternatively `POST /resources` accepting either a single object or an array (content-negotiation via payload shape)
- **Per-Item Results**: The response must indicate the outcome of each item individually — not just overall success or failure:
  ```json
  { "results": [
    { "index": 0, "status": 201, "id": "abc" },
    { "index": 1, "status": 422, "errors": [{"field": "email", "message": "invalid"}] },
    { "index": 2, "status": 201, "id": "xyz" }
  ]}
  ```
- **Partial Success**: Accept `207 Multi-Status` as the response code when some items succeed and others fail. Do not roll back successful items because one failed (unless transactional semantics are required)
- **Transactional vs. Best-Effort**: Decide upfront: either all-or-nothing (rollback on any failure — use `400` if any item fails) or best-effort (process all items, report per-item results — use `207`). Document the behavior clearly
- **Size Limits**: Enforce a maximum batch size (e.g., 100–1000 items). Return `400` with a clear message if exceeded
- **Idempotency**: Bulk endpoints should support the `Idempotency-Key` header — especially important for import flows that may retry on timeout
- **Async Bulk Processing**: For very large batches, accept the batch, return `202 Accepted` with a job ID, and process asynchronously. Client polls the job status endpoint

## In Practice
Method bulk endpoints accept up to 100 items per request, return per-item `207 Multi-Status` results with best-effort semantics (unless transactional semantics are explicitly required), support `Idempotency-Key`, and enforce size limits with clear error messages. Large import jobs (>100 records) use async processing via a `POST /imports` endpoint returning a job ID.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Bulk / Batch Operations**: Don't make clients issue 500 individual requests. A `POST /resources/batch` endpoint with an array body reduces round trips and overhead dramatically. Return per-item results — `207 Multi-Status` with success/failure per index. Decide on transactional vs. best-effort semantics upfront and document it. Enforce a max batch size. Support `Idempotency-Key` for safe retries. For batches larger than your synchronous limit, go async: `202 Accepted` + job ID + status polling. → `engineering-knowledge-repository/api-design/bulk-batch-operations.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — HTTP method and status code semantics for batch operations
- [Idempotency](idempotency.md) — bulk endpoints need idempotency keys for safe retry
- [Pagination Patterns](pagination-patterns.md) — pagination for reading large collections; bulk for writing them
- [Asynchronous Processing](../performance/asynchronous-processing.md) — large batches should be processed asynchronously

---
id: pagination
tags: [pattern, performance, backend, api-design]
surfaces-at: [functional-design, application-design]
related: [query-optimization, n-plus-one-query, restful-resource-design, database-indexing]
complexity: intermediate
---

# Pagination

## What It Is
The technique for dividing large result sets into smaller pages that are fetched incrementally, rather than returning all results in a single response. Pagination is essential for any API or query that might return more than a few hundred rows — unbounded queries are a performance and reliability risk (OOM, timeout, client overload). The choice of pagination strategy has significant implications for performance, correctness, and API usability.

## When to Apply
- Any API endpoint that returns a list of resources (users, orders, events, logs)
- Any database query that could return more than a few hundred rows
- Infinite scroll, load-more, or next-page UI patterns
- Event feeds, audit logs, or time-series data accessed sequentially

## Key Concepts
- **Offset Pagination**: Skip N rows, take M rows. `SELECT * FROM orders LIMIT 20 OFFSET 100`
  - Simple to implement; intuitive API (`?page=5&per_page=20`)
  - **Fatal flaw**: As offset increases, the database scans all preceding rows before discarding them. `OFFSET 10000 LIMIT 20` scans 10,020 rows. Performance degrades linearly with page depth
  - **Consistency flaw**: If rows are inserted or deleted while paginating, pages shift — users see duplicates or miss items
  - Use only for: small datasets (< 10,000 rows total), or user-facing pagination that won't go deep
- **Cursor Pagination (Keyset Pagination)**: Use a stable, indexed cursor (typically the last seen ID or timestamp) to fetch the next page. `SELECT * FROM orders WHERE id > {cursor} ORDER BY id LIMIT 20`
  - **Performance**: O(1) regardless of page depth — uses an index seek, not a scan. Fast at page 10,000 just as at page 1
  - **Consistency**: Stable under concurrent inserts/deletes — new rows don't shift pages
  - **Limitation**: Cannot jump to arbitrary pages (no "go to page 50"); only forward/backward navigation
  - Use for: large datasets, infinite scroll, event feeds, any data accessed sequentially
- **Cursor Encoding**: Return an opaque cursor token (base64-encoded ID + sort key) to clients rather than raw IDs. This decouples the API from the internal implementation and allows changing the cursor strategy without breaking clients
- **Bidirectional Cursors**: Support both `after` (next page) and `before` (previous page) cursors for full forward/backward navigation. `WHERE id > after_cursor OR id < before_cursor`
- **GraphQL Connections**: The Relay cursor pagination spec defines `edges`, `node`, `cursor`, `pageInfo` with `hasNextPage` / `hasPreviousPage`. Standard for GraphQL APIs
- **Time-Based Cursors**: For time-series data or event feeds, use timestamp + ID composite cursor to handle ties (multiple records with the same timestamp). `WHERE (created_at, id) > (cursor_timestamp, cursor_id)`
- **Page Size Limits**: Always enforce a maximum page size server-side — never allow clients to request unlimited results. `?limit=1000000` is an application-layer DoS attack. Typical defaults: 20-50 items; maximum: 100-500
- **Total Count**: Returning total result count (`X-Total-Count` header or `total` field) requires a `COUNT(*)` query which is expensive on large tables. Consider omitting total count for cursor-paginated APIs — "has more pages" is usually sufficient
- **Index Requirements**: Cursor pagination requires an index on the cursor column(s). Composite indexes for multi-column sort orders. Without the right index, cursor pagination performs no better than offset

## In Practice
Method APIs use cursor pagination by default for all list endpoints. Offset pagination is used only for admin interfaces with small, bounded datasets. Cursors are base64-encoded composites of (id, sort_key). Maximum page size is 100; default is 20. Total count is omitted for performance unless explicitly required by the client. GraphQL APIs follow the Relay connection spec.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Pagination**: Offset pagination is a trap — it works fine on small datasets and degrades to a full table scan at depth on large ones. Use cursor pagination (keyset pagination) for any data that might have more than a few thousand rows. Always enforce a server-side page size limit — an unbounded query is a reliability risk. Returning total count on every paginated request is expensive; omit it unless the UI genuinely needs it, and cache it when you do. Ensure indexes exist on the cursor column before deploying cursor pagination — it's just an expensive scan otherwise. → `engineering-knowledge-repository/pagination.md`

## Related Entries
- [Query Optimization](query-optimization.md) — pagination strategy selection is a query optimization decision
- [N+1 Query](n-plus-one-query.md) — eager loading related data is essential when paginating list results
- [Database Indexing](database-indexing.md) — cursor pagination requires indexes on cursor columns for performance
- [RESTful Resource Design](restful-resource-design.md) — pagination parameters and response envelope are part of REST API design

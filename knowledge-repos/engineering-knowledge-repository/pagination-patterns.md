---
id: pagination-patterns
tags: [pattern, api-design, backend]
surfaces-at: [application-design, functional-design]
related: [rest-constraints, query-optimization, api-first-design, response-envelope-pattern]
complexity: intermediate
---

# Pagination Patterns

## What It Is
The strategy for returning large collections of resources in bounded, navigable pages rather than all at once. Unbounded collection endpoints are a reliability and performance hazard — a single request can return millions of rows. All collection endpoints should be paginated by default. The two dominant strategies are offset-based and cursor-based pagination, each with distinct tradeoffs.

## When to Apply
- Any API endpoint that returns a collection of resources
- Always — paginate by default; never return unbounded collections

## Key Concepts
- **Offset Pagination**: `GET /orders?page=2&limit=20` — skip N rows, return the next M. Simple to implement, easy to navigate to arbitrary pages. Problem: as data is inserted or deleted, rows shift — a page 2 request may skip or repeat items. Degrades at high offsets (`OFFSET 100000` requires scanning 100,000 rows)
- **Cursor Pagination**: `GET /orders?after=cursor_xyz&limit=20` — the cursor encodes the position (typically the last item's ID or sort key). Stable: insertions don't shift results. Efficient: the query uses an index seek rather than a scan. Cannot jump to arbitrary pages
- **Keyset Pagination**: A variant of cursor pagination that uses the actual values of sort columns rather than an opaque cursor — `WHERE created_at < '2024-01-15' AND id < 999`. More transparent, easier to debug
- **`Link` Header**: RFC 5988 — include `rel=next`, `rel=prev`, `rel=first`, `rel=last` links in the response header. Clients follow links rather than constructing URLs
- **`meta` Block**: Include `{ "total": 10432, "page": 2, "per_page": 20 }` for offset pagination where total count is needed for UI display
- **Page Size Limits**: Enforce a maximum page size (e.g., 100). Allow clients to request smaller pages. Never allow unlimited
- **Default Page Size**: Always set a sensible default (20–50). Never require clients to specify a page size to get bounded results

## In Practice
Method APIs use cursor pagination for all high-volume, append-heavy collections (events, transactions, audit logs). Offset pagination is acceptable for small, stable datasets where arbitrary page navigation is required (admin UIs). Cursors are opaque base64-encoded tokens — implementation details (IDs, timestamps) are not exposed. Maximum page size: 100. Default: 20.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Pagination Patterns**: Never return unbounded collections. Default to cursor pagination for large or fast-changing datasets — it's stable (inserts don't shift pages) and efficient (index seek, not scan). Use offset only when arbitrary page navigation is required and datasets are small and stable. Encode cursors as opaque base64 tokens. Enforce a max page size. Include `Link` headers with `rel=next`/`rel=prev`. → `engineering-knowledge-repository/api-design/pagination-patterns.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — pagination is a core REST collection design concern
- [Query Optimization](../performance/query-optimization.md) — high-offset queries are a performance anti-pattern; cursor pagination avoids them
- [Response Envelope Pattern](response-envelope-pattern.md) — pagination metadata is often returned in an envelope wrapper

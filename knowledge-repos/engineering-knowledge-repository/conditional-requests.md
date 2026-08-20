---
id: conditional-requests
tags: [pattern, api-design, backend, network]
surfaces-at: [application-design, functional-design, nfr-requirements]
related: [rest-constraints, caching-strategies, cdn-pattern, idempotency, optimistic-locking]
complexity: intermediate
---

# Conditional Requests

## What It Is
HTTP conditional requests allow clients to make requests that only execute if a specified condition is met — typically based on a resource's version (ETag) or last modification time. They serve two distinct purposes: **cache validation** (only re-fetch if changed) and **optimistic concurrency control** (only update if nobody else has changed it since I last read it). Both eliminate unnecessary work and prevent lost updates.

## When to Apply
- Any GET endpoint for resources that change infrequently — conditional requests enable efficient cache revalidation
- Any PUT or PATCH endpoint where concurrent modification is a risk — conditional writes prevent lost updates
- APIs consumed by mobile clients or high-latency environments where avoiding unnecessary data transfer matters

## When Not to Apply
- Write-heavy endpoints with no concurrent modification risk
- Simple internal APIs where the overhead of ETag generation is not worth the benefit

## Key Concepts

**ETags (Entity Tags)**
- A server-generated opaque string representing a specific version of a resource — typically a hash of the content or a version number
- Strong ETag: `"abc123"` — byte-for-byte identical. Weak ETag: `W/"abc123"` — semantically equivalent but may differ in representation

**Cache Validation (`If-None-Match` / `If-Modified-Since`)**
- Client caches a response and stores the ETag and/or `Last-Modified` date
- On next request: `If-None-Match: "abc123"` or `If-Modified-Since: Tue, 15 Jan 2025 10:00:00 GMT`
- If unchanged: server returns `304 Not Modified` with no body — client uses its cached copy
- If changed: server returns `200 OK` with new content and new ETag
- Result: bandwidth savings and reduced server load for unchanged resources

**Optimistic Concurrency (`If-Match` / `If-Unmodified-Since`)**
- Client reads a resource and captures its ETag
- On update: `PUT /resources/123` with `If-Match: "abc123"`
- If resource hasn't changed since the client read it: update proceeds (`200 OK`)
- If another client has modified it: `412 Precondition Failed` — the client must re-fetch and re-apply their change
- Prevents the lost update problem without pessimistic locking

**`Last-Modified` Header**
- An alternative to ETags using a timestamp — less precise (1-second granularity) but simpler to implement
- Used with `If-Modified-Since` (cache validation) and `If-Unmodified-Since` (concurrency control)

**`Vary` Header**
- Tells caches which request headers affect the response representation — `Vary: Accept-Encoding, Accept-Language`
- Essential for content-negotiated responses so caches don't serve the wrong representation

## In Practice
Method APIs include ETags on all resource GET responses. `If-None-Match` support reduces mobile client bandwidth usage. `If-Match` is required on PUT/PATCH for all resources where concurrent modification is possible — the API returns `412` on conflict, and clients are expected to re-fetch, merge, and retry. ETags are generated as a hash of the resource content.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Conditional Requests**: Two use cases, different headers. Cache validation: client sends `If-None-Match: "etag"` on GET; server returns `304 Not Modified` if unchanged — saves bandwidth. Optimistic concurrency: client sends `If-Match: "etag"` on PUT/PATCH; server returns `412 Precondition Failed` if someone else modified it first — prevents lost updates without locking. Include ETags on all resource GET responses. Require `If-Match` on mutation endpoints where concurrent modification is a risk. → `engineering-knowledge-repository/conditional-requests.md`

## Related Entries
- [REST Constraints](rest-constraints.md) — conditional requests are a core HTTP/REST caching and safety mechanism
- [Caching Strategies](caching-strategies.md) — conditional requests enable efficient cache revalidation at the HTTP layer
- [CDN Pattern](cdn-pattern.md) — CDNs use ETags and Last-Modified for cache revalidation with origin servers
- [Idempotency](idempotency.md) — conditional requests provide a complementary concurrency safety mechanism to idempotency keys
- [Optimistic Locking](optimistic-locking.md) — conditional requests are the HTTP-native implementation of optimistic locking

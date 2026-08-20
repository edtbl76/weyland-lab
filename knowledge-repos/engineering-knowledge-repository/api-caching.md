---
id: api-caching
tags: [pattern, api-design, performance, backend]
surfaces-at: [application-design, nfr-requirements]
related: [conditional-requests, cdn-pattern, api-gateway-design, rest-constraints, api-rate-limiting-design]
complexity: intermediate
---

# API Caching

## What It Is
Storing API responses so that identical or equivalent requests can be served from cache without re-executing the underlying computation or database query. Caching is one of the highest-leverage performance and cost optimizations available to API designers — it reduces latency, database load, and infrastructure cost simultaneously. Effective API caching requires understanding cache location (client, CDN, gateway, server), cache scope (public vs. private), invalidation strategy, and the tradeoffs between cache freshness and performance.

## When to Apply
- Read-heavy endpoints where the same data is requested frequently
- Responses that are expensive to compute (aggregations, external API calls, ML inference)
- Static or slowly changing resources (reference data, configuration, catalog items)
- Any endpoint where latency reduction or backend load reduction is a goal

## Key Concepts
- **Cache-Control Header**: The primary mechanism for communicating caching behavior. Key directives:
  - `max-age=N`: Cache is valid for N seconds
  - `no-cache`: Must revalidate with server before using cached response (can still cache)
  - `no-store`: Never cache — for sensitive data
  - `public`: Can be cached by shared caches (CDNs, proxies)
  - `private`: Only client-side caching — not for CDN or shared proxy caches
  - `s-maxage=N`: Override `max-age` for shared caches (CDNs) specifically
- **ETag and Conditional Requests**: Server returns an `ETag` (hash of response content). Client sends `If-None-Match: <etag>` on subsequent requests. Server returns 304 Not Modified (no body) if unchanged — saves bandwidth. See Conditional Requests entry
- **Vary Header**: Tells caches which request headers affect the response — `Vary: Accept-Encoding, Accept-Language`. Caches store separate entries per Vary value combination. Incorrect Vary leads to wrong cached responses being served
- **CDN Caching**: Public `Cache-Control` headers enable CDNs (CloudFront, Fastly) to cache responses at edge locations globally. Dramatic latency reduction for geographically distributed clients. Requires `public` cache-control and appropriate `max-age`
- **API Gateway Caching**: Cache responses at the gateway layer (AWS API Gateway, Kong, Apigee). Reduces load on backend services. Useful for expensive endpoints that don't vary significantly per request
- **Cache Invalidation**: The hard problem. Strategies: TTL-based expiry (simple, eventual consistency), event-driven invalidation (purge cache on data change — complex, precise), versioned URLs (content-addressable — cache forever, change URL on update)
- **Cache Scope**:
  - *Client cache*: Browser or API client — `private`, `max-age`
  - *Shared/CDN cache*: Edge nodes — `public`, `s-maxage`
  - *Server-side cache*: Redis/Memcached in the API layer — transparent to HTTP caching headers
- **What Not to Cache**: Authenticated user-specific responses with `public` (cache poisoning risk), rapidly changing data with long TTLs, POST/PUT/DELETE responses (non-idempotent — do not cache)

## In Practice
Method APIs set explicit `Cache-Control` headers on all GET endpoints. Public reference data uses `public, max-age=3600, s-maxage=86400` for CDN caching. User-specific data uses `private, max-age=60`. ETags are generated for all resource responses to enable conditional requests. API Gateway response caching is enabled for expensive read-heavy endpoints.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — API Caching**: Set explicit Cache-Control headers on every GET endpoint — no header means each client and intermediary makes its own caching decision. Use `public` + `s-maxage` to enable CDN caching for non-personalized responses. Never cache user-specific data with `public` — it will serve one user's data to another. ETags enable efficient revalidation — return 304 with no body when content hasn't changed. Cache invalidation is the hard part — prefer short TTLs over complex invalidation logic unless performance requires it. `no-store` for anything sensitive; `private` for authenticated user responses. → `engineering-knowledge-repository/api-caching.md`

## Related Entries
- [Conditional Requests](conditional-requests.md) — ETags and If-None-Match implement cache revalidation
- [CDN Pattern](cdn-pattern.md) — CDNs serve as the shared cache layer for public API responses
- [API Gateway Design](api-gateway-design.md) — API gateways can cache responses before requests reach backend services
- [REST Constraints](rest-constraints.md) — cacheability is one of the six REST architectural constraints
- [API Rate Limiting Design](api-rate-limiting-design.md) — caching reduces request volume, complementing rate limiting

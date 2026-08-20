---
id: cdn-pattern
tags: [pattern, performance, network, cloud, infrastructure]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [caching-strategies, edge-computing, cloud-native-design, cloud-cost-optimization]
complexity: foundational
---

# CDN Pattern

## What It Is
A Content Delivery Network (CDN) is a geographically distributed network of cache servers (Points of Presence — PoPs) that serve content from the location closest to the user. Rather than every request traveling to the origin server, the CDN serves cached responses from the nearest edge node — reducing latency, offloading origin traffic, and improving availability. CDNs are used for static assets (JS, CSS, images), cacheable API responses, and increasingly for edge compute.

## When to Apply
- Any web application with geographically distributed users
- Static assets (JS bundles, CSS, images, fonts) — should always be CDN-served
- Cacheable API responses with high read-to-write ratios
- Protection against traffic spikes — CDN absorbs surge traffic without hitting origin

## When Not to Apply
- Highly dynamic, personalized content that cannot be cached
- Internal applications with users in a single location where latency is already low
- APIs with no caching headers — a CDN won't cache without proper Cache-Control headers

## Key Concepts
- **Cache-Control Headers**: Instruct the CDN (and browsers) how long to cache a response. `Cache-Control: public, max-age=31536000, immutable` for versioned static assets; `Cache-Control: no-store` for sensitive responses
- **Cache Invalidation**: Clearing cached content before TTL expiry. Most CDNs support purge by URL or tag. Versioned asset URLs (`main.abc123.js`) avoid invalidation entirely
- **Origin Shield**: A mid-tier CDN cache that absorbs requests before they reach origin — reduces origin load dramatically for large-scale traffic
- **CDN Providers**: Cloudflare (most feature-rich, includes edge compute), AWS CloudFront (native AWS integration), Fastly (programmable CDN)
- **Cache Hit Ratio**: The percentage of requests served from CDN cache vs. forwarded to origin. Target 90%+ for static assets. Low ratio = incorrect Cache-Control headers
- **Geo-Routing**: CDNs route users to the nearest PoP — the primary latency benefit
- **HTTPS Termination**: CDNs handle TLS termination at the edge — reducing TLS handshake overhead for end users

## In Practice
Method uses CloudFront for AWS-hosted applications (tight integration with S3, ALB, Lambda@Edge) and Cloudflare for applications requiring edge compute alongside CDN. All static assets are served via CDN with immutable cache headers and content-addressed filenames. API responses with stable, non-personalized content (product catalogs, reference data) are CDN-cached with appropriate TTLs.

## Engineering Knowledge
💡 **Engineering Knowledge — CDN Pattern**: Every web application should serve static assets via CDN — it's one of the highest-ROI infrastructure decisions. Use versioned filenames (`app.abc123.js`) with `Cache-Control: immutable` and never worry about cache invalidation for assets. For API responses, add `Cache-Control: public, max-age=60` where data is non-personalized and tolerates staleness. Monitor cache hit ratio — below 85% means caching headers need work. Cloudflare and CloudFront both provide DDoS protection and TLS termination as part of CDN. → `engineering-knowledge-repository/performance/cdn-pattern.md`

## Related Entries
- [Caching Strategies](caching-strategies.md) — CDN is the outermost layer of the caching hierarchy
- [Edge Computing](../cloud-patterns/edge-computing.md) — edge computing extends CDN from caching to computation
- [Cloud-Native Design](../cloud-patterns/cloud-native-design.md) — CDN is a core component of cloud-native web architecture
- [Cloud Cost Optimization](../cloud-patterns/cloud-cost-optimization.md) — CDN reduces origin compute costs by absorbing traffic

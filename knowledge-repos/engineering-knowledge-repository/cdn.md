---
id: cdn
tags: [pattern, infrastructure, performance, reliability]
surfaces-at: [infrastructure-design, application-design]
related: [caching-strategies, web-performance, server-side-rendering, load-balancing]
complexity: foundational
---

# CDN (Content Delivery Network)

## What It Is
A globally distributed network of edge servers that caches and serves content from locations geographically close to users. Instead of every request traveling to a single origin server in one data center, CDN edge nodes serve cached responses from the nearest point of presence (PoP). This reduces latency, absorbs traffic spikes, and offloads the origin server. CDNs are standard infrastructure for static assets (JS, CSS, images), static sites, and cacheable API responses — and are the most impactful single change for web performance globally distributed users.

## When to Apply
- Any web application serving static assets (JS, CSS, images, fonts)
- Static-generated sites and marketing pages
- Applications with a geographically distributed user base
- APIs with cacheable responses that benefit from edge distribution
- High-traffic applications where origin server capacity is a concern

## Key Concepts
- **Edge Nodes (PoPs)**: CDN provider operates hundreds of data centers globally. User requests route to the nearest PoP; if cached, the response is served without hitting the origin. If not cached (cache miss), the edge fetches from origin, caches, and serves
- **Cache-Control Headers**: The origin server controls CDN caching behavior via `Cache-Control` response headers:
  - `Cache-Control: public, max-age=31536000, immutable` — cache for 1 year; never revalidate. For content-hashed static assets
  - `Cache-Control: public, s-maxage=3600, stale-while-revalidate=86400` — CDN caches for 1 hour; serves stale while revalidating for 24 hours. For semi-dynamic pages
  - `Cache-Control: private, no-store` — never cache. For authenticated, personalized responses
- **Cache Invalidation**: CDN caches must be purged when content changes. Strategies:
  - *Content-hash filenames*: `main.abc123.js` — when content changes, the filename changes, and the URL changes. Old URL stays cached; new URL has no cache. No invalidation needed — the most robust approach
  - *CDN purge API*: Programmatic cache purge on deploy. Available in all major CDNs. Use for HTML files and server-rendered pages
- **Major Providers**:
  - *CloudFront (AWS)*: Deep AWS integration; Lambda@Edge and CloudFront Functions for edge compute; S3 origin for static sites
  - *Cloudflare*: Extensive global network; Workers for edge compute; DDoS protection included; zero-trust network features
  - *Fastly*: VCL-based configuration; real-time analytics; popular for APIs and high-traffic media
  - *Akamai*: Largest network; enterprise-focused; strong media delivery
- **Edge Compute**: Modern CDNs support running JavaScript at the edge (CloudFront Functions, Cloudflare Workers, Vercel Edge Functions). Enables personalization, A/B testing, authentication, and request transformation without round-tripping to origin
- **CDN for APIs**: APIs with cacheable responses (product listings, public data, search results) benefit from CDN caching. Requires careful cache key design — include query parameters that affect response. `Vary` header controls caching by request headers (Accept-Language, Accept-Encoding)
- **CDN for Images**: CDNs with image optimization (Cloudflare Images, Cloudinary, imgix, CloudFront with Lambda@Edge) resize, format-convert (WebP, AVIF), and compress images on the fly. Eliminates the need to pre-generate all image variants
- **HTTPS and TLS**: CDNs terminate TLS at the edge, reducing TLS handshake latency for users. CloudFront and Cloudflare manage certificates automatically via ACM or Let's Encrypt

## In Practice
Method uses CloudFront for all AWS-hosted applications. Static assets are served from S3 via CloudFront with `Cache-Control: immutable` and content-hash filenames. HTML pages use `s-maxage=3600` with CDN purge on deploy. CloudFront Functions handle auth token validation at the edge. Cloudflare is used when DDoS protection and edge compute are primary requirements.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — CDN**: The fastest way to improve global web performance is to put a CDN in front of static assets — this is table stakes, not an optimization. Use content-hash filenames for JS/CSS bundles and set `Cache-Control: immutable` — this eliminates cache invalidation complexity entirely. Cache HTML pages at the CDN with a short TTL (`s-maxage=3600`) and purge on deploy. Never cache authenticated or personalized responses at the CDN layer — use `Cache-Control: private`. Edge compute (Cloudflare Workers, CloudFront Functions) is increasingly powerful for auth, personalization, and API routing at the edge. → `engineering-knowledge-repository/cdn.md`

## Related Entries
- [Caching Strategies](caching-strategies.md) — CDN is the HTTP caching layer for the edge; cache-control header strategy determines CDN behavior
- [Web Performance](web-performance.md) — CDN placement reduces latency globally and is one of the highest-impact performance improvements
- [Server-Side Rendering](server-side-rendering.md) — SSG pages are served from CDN; ISR pages cache at the CDN with revalidation
- [Load Balancing](load-balancing.md) — CDNs route to origin load balancers on cache miss

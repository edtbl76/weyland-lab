---
id: compression
tags: [pattern, performance, backend, infrastructure]
surfaces-at: [application-design, infrastructure-design]
related: [cdn, web-performance, api-gateway-design, storage-patterns, data-serialization-formats]
complexity: foundational
---

# Compression

## What It Is
Reducing the size of data in transit or at rest to decrease bandwidth consumption, reduce latency, and lower storage costs. For HTTP APIs and web applications, compression is one of the highest-ROI performance improvements — typically reducing response body size by 60-80% with minimal CPU overhead. Compression is almost always worth enabling at the HTTP layer; the CPU cost of compression is negligible compared to the bandwidth savings.

## When to Apply
- Every HTTP server serving text-based content (HTML, JSON, CSS, JavaScript)
- Large API responses (list endpoints, reports, bulk exports)
- Static assets served from web servers or CDNs
- Any storage scenario where the data is compressible and storage cost matters

## Key Concepts
- **HTTP Compression**: Client advertises support via `Accept-Encoding: gzip, br, deflate` header; server responds with compressed body and `Content-Encoding: gzip` header. Transparent to application code when handled at the server/middleware layer
  - *gzip*: The universal standard. Supported by all HTTP clients and servers. Typically 60-70% compression ratio for JSON
  - *Brotli (br)*: Google's algorithm; 20-30% better compression than gzip. Supported by all modern browsers and many proxies. Use Brotli for static assets served from CDN; gzip for dynamic API responses (Brotli has higher compression CPU cost)
  - *Deflate*: Avoid — implementation inconsistencies between clients/servers; use gzip instead
  - *zstd*: Fast compression; excellent for server-to-server API calls where both sides control the stack. Not universally supported in browsers
- **Minimum Size Threshold**: Don't compress small responses — the overhead of compression headers exceeds the savings for responses < 1KB. Most servers default to 1KB threshold; 256 bytes is a reasonable minimum
- **Content Types to Compress**: Text-based: JSON, XML, HTML, CSS, JavaScript, SVG, plain text. Do NOT compress already-compressed formats: JPEG, PNG, WebP, MP4, ZIP, gzip — double-compressing actually increases size
- **Server Configuration**:
  - *nginx*: `gzip on; gzip_types application/json text/html text/css application/javascript; gzip_min_length 1000;`
  - *Express (Node.js)*: `compression` middleware — `app.use(compression())`
  - *FastAPI/uvicorn*: `GZipMiddleware` — `app.add_middleware(GZipMiddleware, minimum_size=1000)`
  - *AWS ALB*: Does not compress; use nginx or app-level compression, or CloudFront with compression enabled
  - *CloudFront*: Enable "Compress Objects Automatically" — compresses at the edge, caches compressed versions
- **Static Asset Compression**: Pre-compress static assets at build time (gzip + Brotli) and serve the pre-compressed file directly. Eliminates runtime compression CPU cost. Vite, webpack, and nginx can all serve pre-compressed files
- **API Response Compression**: Enable at the reverse proxy (nginx) or application middleware layer. Verify with `curl -H "Accept-Encoding: gzip" -v https://api.example.com/endpoint | gunzip` — `Content-Encoding: gzip` in response headers confirms it's working
- **Database Compression**: PostgreSQL's TOAST mechanism automatically compresses large column values. Storage-engine compression (PostgreSQL page compression, MySQL InnoDB compression) reduces disk footprint at the cost of CPU. Generally worth enabling for data warehouse or cold-data tables

## In Practice
Method enables gzip compression via nginx for all API responses above 1KB. CloudFront serves pre-compressed Brotli and gzip versions of static assets. JSON API responses average 65% size reduction with gzip enabled. Large bulk export endpoints (CSV, JSON reports) use streaming gzip compression to avoid buffering entire responses in memory.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Compression**: Enable HTTP compression on every API server — it's 2 lines of config and reduces JSON response sizes by 60-80%. Use Brotli for static assets (served from CDN with pre-compressed files) and gzip for dynamic API responses. Never compress already-compressed formats (images, video, zip files) — you'll make them larger. Verify compression is actually working with `curl -H "Accept-Encoding: gzip" -v` — it's surprisingly common for compression to be configured but not applied due to middleware order issues. For bulk data exports, use streaming compression to avoid OOM from buffering large responses. → `engineering-knowledge-repository/compression.md`

## Related Entries
- [CDN](cdn.md) — CDNs compress and cache static assets at the edge, eliminating per-origin-request compression cost
- [Web Performance](web-performance.md) — compression reduces bundle transfer size, directly improving LCP
- [Storage Patterns](storage-patterns.md) — database and object storage compression reduce storage costs for compressible data
- [Data Serialization Formats](data-serialization-formats.md) — binary serialization formats (Protocol Buffers, Avro) are smaller than JSON even before compression

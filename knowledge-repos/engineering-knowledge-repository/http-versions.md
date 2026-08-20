---
id: http-versions
tags: [protocol, network, performance]
surfaces-at: [application-design, nfr-design]
related: [web-performance, cdn, grpc, rest-constraints, compression, load-balancing]
complexity: intermediate
---

# HTTP Versions

## What It Is
The evolution of the Hypertext Transfer Protocol from HTTP/1.1 through HTTP/2 to HTTP/3 — each version addressing fundamental performance limitations of its predecessor. The version of HTTP a service uses has significant, measurable impact on latency, throughput, and connection overhead. HTTP/1.1 has dominated the web for 20+ years; HTTP/2 became mainstream in the 2010s; HTTP/3 (based on QUIC) is now broadly supported and offers meaningful advantages for high-latency and lossy network conditions. Understanding which version to use — and why — is part of a complete web performance strategy.

## When to Apply
- Configuring load balancers, CDNs, and application servers for new services
- Diagnosing latency issues where connection overhead is a factor
- Designing APIs that serve mobile clients on variable-quality networks
- Evaluating CDN providers (HTTP/2 and HTTP/3 support varies)
- gRPC adoption decisions (gRPC requires HTTP/2)

## Key Concepts
- **HTTP/1.1**: Released 1997, still dominant in many server-to-server connections. Key limitations:
  - *Head-of-line blocking*: Requests on a connection are processed in order; a slow request blocks all subsequent requests on that connection
  - *Connection limitations*: Browsers open 6 TCP connections per origin to work around HOL blocking, creating connection overhead
  - *Text-based headers*: Headers sent as plaintext on every request (no compression)
  - Still appropriate for: internal service-to-service communication where connection overhead is low and request volumes are moderate

- **HTTP/2**: Released 2015. Addresses HTTP/1.1 performance limitations with:
  - *Multiplexing*: Multiple requests/responses over a single TCP connection simultaneously — eliminates the need for multiple connections
  - *Header compression (HPACK)*: Headers compressed across requests; repeated headers (cookies, auth) sent only as deltas
  - *Server Push*: Server can proactively send resources before client requests them (limited adoption in practice)
  - *Binary protocol*: Binary framing instead of text parsing
  - *Limitation*: TCP head-of-line blocking still exists — packet loss on the TCP layer stalls all multiplexed streams
  - Adoption: All major browsers and load balancers support HTTP/2. CDNs (CloudFront, Cloudflare) serve HTTP/2 to browsers by default

- **HTTP/3**: Released 2022 (IETF RFC 9114). Based on QUIC (originally Google's QUIC, now standardized):
  - *UDP-based*: QUIC runs over UDP, eliminating TCP's connection establishment overhead and head-of-line blocking
  - *0-RTT connection resumption*: Resuming a known connection takes 0 round trips (vs. TCP's 1-RTT + TLS 1-3's 1-RTT = 2 RTTs for HTTP/2)
  - *Connection migration*: Connections survive IP address changes (mobile users moving between WiFi and cellular)
  - *Stream independence*: Packet loss on one QUIC stream doesn't block other streams (fixes HTTP/2's TCP HOL blocking)
  - *Best for*: Mobile clients, high-latency networks, applications where connection establishment latency matters
  - Adoption: Cloudflare, AWS CloudFront, Google, and major CDNs support HTTP/3. Enabled by default in Cloudflare. Requires explicit configuration in nginx/envoy

- **Version Negotiation**: Clients and servers negotiate the highest mutually supported version. Browsers use ALPN (Application-Layer Protocol Negotiation) in TLS handshake. CDNs typically terminate HTTP/2 or HTTP/3 from browsers and use HTTP/1.1 or HTTP/2 for origin connections
- **gRPC and HTTP/2**: gRPC requires HTTP/2 — it uses HTTP/2 multiplexing for bidirectional streaming. Ensure load balancers and proxies support HTTP/2 for gRPC traffic

## In Practice
Method's frontend services are served via CloudFront with HTTP/2 (and HTTP/3 where enabled). Origin-to-CDN connections use HTTP/2. Internal service-to-service traffic uses HTTP/1.1 with connection pooling for simple REST calls; gRPC services use HTTP/2. HTTP/3 is evaluated on a per-engagement basis for mobile-first applications where 0-RTT and connection migration provide measurable user experience improvements.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — HTTP Versions**: HTTP/2 is the default for browser-facing traffic — your CDN should be serving it already. The main HTTP/2 win is header compression and multiplexing for pages with many assets. HTTP/3 matters most on mobile and high-latency networks; if your user base skews mobile, measure the 0-RTT and connection migration benefits before deciding not to enable it. gRPC requires HTTP/2 end-to-end — verify that every proxy and load balancer in the path supports HTTP/2 before deploying gRPC. Server push (HTTP/2 and HTTP/3) looks appealing but is rarely worth the implementation complexity over link preload headers. → `engineering-knowledge-repository/http-versions.md`

## Related Entries
- [Web Performance](web-performance.md) — HTTP/2 and HTTP/3 are infrastructure-level web performance improvements
- [CDN](cdn.md) — CDNs negotiate HTTP versions with browsers; CloudFront and Cloudflare support HTTP/2 and HTTP/3
- [gRPC](grpc.md) — gRPC requires HTTP/2 throughout the request path
- [REST Constraints](rest-constraints.md) — REST can operate over any HTTP version; HTTP/2 improves REST API performance
- [Compression](compression.md) — HTTP header compression (HPACK in HTTP/2, QPACK in HTTP/3) complements body compression
- [Load Balancing](load-balancing.md) — load balancers must support HTTP/2 passthrough or termination for gRPC and HTTP/2 clients

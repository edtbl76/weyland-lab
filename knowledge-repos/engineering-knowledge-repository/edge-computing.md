---
id: edge-computing
tags: [pattern, cloud, infrastructure, performance, network]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [cdn-pattern, cloud-native-design, serverless, caching-strategies]
complexity: intermediate
---

# Edge Computing

## What It Is
The execution of compute logic at locations geographically close to users — CDN edge nodes, regional PoPs (Points of Presence), or 5G edge infrastructure — rather than in a centralized data center or cloud region. Edge computing reduces latency by eliminating the round trip to a distant origin server, enables regional content customization, and offloads compute from origin. Examples: Cloudflare Workers, AWS Lambda@Edge, Fastly Compute@Edge.

## When to Apply
- Applications with geographically distributed users where latency is a priority NFR
- A/B testing, feature flagging, and personalization that must happen before content is served
- Authentication and authorization checks that should not incur a round trip to origin
- Traffic routing, geo-blocking, and bot mitigation
- Static asset serving and HTML edge rendering for performance

## When Not to Apply
- Compute-heavy operations that require significant resources unavailable at the edge
- Applications with complex stateful logic that requires centralized consistency
- Small applications with geographically concentrated user bases where the complexity isn't warranted
- Workloads requiring access to centralized databases not available at the edge

## Key Concepts
- **Edge Functions**: Short-lived, stateless compute units running on CDN edge nodes (Cloudflare Workers, Lambda@Edge). Execution time is typically limited (50ms CPU for Workers)
- **Edge Caching**: Cache responses at the CDN layer — content served from edge without hitting origin. Cache-Control headers and cache keys control behavior
- **Edge Routing**: Route requests to different origins based on geography, user attributes, or canary rules — without a round trip to origin
- **KV at Edge**: Cloudflare Workers KV and similar stores provide key-value access at the edge for low-latency reads. Eventual consistency — not suitable for write-heavy workloads
- **Cold Start Considerations**: Unlike Lambda (which has VMs), edge functions use V8 Isolates — cold starts are typically sub-millisecond but have execution constraints
- **Durable Objects (Cloudflare)**: Stateful edge primitives with strong consistency — each object is a single-threaded actor with its own storage

## In Practice
Edge computing for Method engagements is primarily CDN-level: caching, geo-routing, and lightweight middleware (auth checks, header manipulation). Cloudflare Workers are used for edge middleware in performance-sensitive applications. Full application logic at the edge is reserved for cases where sub-10ms latency is a hard requirement. The operational complexity of edge deployments should be weighed against the latency gains for most business applications.

## Engineering Knowledge
💡 **Engineering Knowledge — Edge Computing**: Run logic at CDN edge nodes to eliminate origin round trips for geographically distributed users. Cloudflare Workers and Lambda@Edge are suited for lightweight middleware — auth checks, A/B routing, geo-blocking, personalization headers. They are not suited for heavy compute or stateful operations. Edge caching is the highest-ROI lever: keep static assets and cacheable API responses at the edge and never hit origin for them. Measure P99 latency before and after — edge adds complexity; verify the gain justifies it. → `engineering-knowledge-repository/cloud-patterns/edge-computing.md`

## Related Entries
- [CDN Pattern](../performance/cdn-pattern.md) — edge computing extends CDN from static caching to compute
- [Cloud-Native Design](cloud-native-design.md) — edge is the furthest-distributed layer of cloud-native architectures
- [Serverless](../architectural-styles/serverless.md) — edge functions are a serverless execution model at the edge
- [Caching Strategies](../performance/caching-strategies.md) — edge caching is a critical layer in the caching hierarchy

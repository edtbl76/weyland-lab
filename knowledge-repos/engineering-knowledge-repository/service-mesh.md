---
id: service-mesh
tags: [pattern, distributed-systems, microservices, infrastructure]
surfaces-at: [infrastructure-design, nfr-design]
related: [microservices, api-gateway-pattern, circuit-breaker, bulkhead-pattern, sidecar-pattern]
complexity: advanced
---

# Service Mesh

## What It Is
A dedicated infrastructure layer for handling service-to-service communication in microservices systems. A service mesh implements cross-cutting networking concerns — traffic management, observability (traces, metrics, logs), security (mTLS), circuit breaking, retries, and load balancing — in a sidecar proxy deployed alongside each service, rather than in the application code itself. Common implementations: Istio (with Envoy proxy), Linkerd, AWS App Mesh, Consul Connect.

## When to Apply
- Microservices systems where networking concerns (retries, circuit breaking, mTLS) are currently implemented inconsistently across services
- When you need uniform observability (distributed tracing, service maps) across all services without modifying application code
- When zero-trust networking (mTLS between all services) is a security requirement
- Large-scale microservices deployments where cross-cutting concerns at the network layer become a platform problem

## When Not to Apply
- Small or medium microservices deployments — the operational overhead (sidecar proxies, control plane, configuration complexity) often exceeds the benefit
- Teams without Kubernetes or container orchestration expertise — service meshes are complex infrastructure
- When simpler alternatives (application-level circuit breakers, API gateway rate limiting) are sufficient for current needs

## Key Concepts
- **Data Plane**: The sidecar proxies (typically Envoy) deployed alongside each service instance — intercept all inbound and outbound traffic
- **Control Plane**: Manages and configures the data plane proxies (Istio's istiod) — distributes traffic policies, certificates, and telemetry configuration
- **Sidecar Proxy**: A co-deployed proxy container that intercepts all traffic to/from the service — the service is unaware of the proxy
- **mTLS (Mutual TLS)**: The mesh can transparently encrypt and authenticate all service-to-service communication without application changes
- **Traffic Management**: Fine-grained routing rules — canary deployments, A/B testing, fault injection for chaos engineering, traffic splitting
- **Observability**: Automatic distributed traces, service topology maps, and golden signal metrics without application instrumentation

## In Practice
Service mesh is enterprise-grade infrastructure. Method recommends evaluating it when a client has 10+ services and networking concerns are becoming inconsistent across teams. The Istio + Envoy stack is the most capable but most complex; Linkerd is simpler and often sufficient. The most immediate value is usually observability (automatic distributed tracing) and security (mTLS). Manage the control plane as code (Helm charts, Istio operator).

## Engineering Knowledge
💡 **Engineering Knowledge — Service Mesh**: In large microservices systems, every service ends up reimplementing retries, circuit breaking, and logging. A service mesh moves all of that to the sidecar proxy layer — services focus on business logic, the mesh handles networking. You get uniform mTLS, distributed traces, and traffic management across every service without touching application code. High operational overhead: don't adopt until you have 10+ services and real cross-cutting networking problems. → `engineering-knowledge-repository/architectural-styles/service-mesh.md`

## Related Entries
- [Microservices](microservices.md) — service mesh is infrastructure for large microservices systems
- [Sidecar Pattern](../infrastructure/sidecar-pattern.md) — the deployment model that enables service mesh
- [Circuit Breaker](../infrastructure/circuit-breaker.md) — service mesh can implement circuit breaking at the proxy layer
- [API Gateway Pattern](api-gateway-pattern.md) — API gateway handles north-south traffic; service mesh handles east-west (service-to-service)

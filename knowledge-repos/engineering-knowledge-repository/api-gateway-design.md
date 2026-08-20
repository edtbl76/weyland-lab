---
id: api-gateway-design
tags: [pattern, api-design, infrastructure, network, microservices]
surfaces-at: [application-design, infrastructure-design]
related: [api-rate-limiting-design, api-security, service-discovery, microservices, long-polling-sse-websockets]
complexity: intermediate
---

# API Gateway Design

## What It Is
An API gateway is a single entry point that sits in front of backend services and handles cross-cutting concerns — authentication, rate limiting, routing, protocol translation, request/response transformation, observability, and TLS termination. Without a gateway, each service must implement these concerns independently; the gateway centralizes them. Common implementations: AWS API Gateway, Kong, Nginx, Envoy, Traefik.

## When to Apply
- Microservices architectures with multiple services exposed to clients
- Any system with external-facing APIs that require auth, rate limiting, or routing
- Multi-protocol environments (REST, gRPC, WebSocket) where a single client-facing interface is needed

## When Not to Apply
- Single-service applications — a gateway adds unnecessary infrastructure
- Internal service-to-service communication — use a service mesh instead; gateways are for north-south traffic (client → service), service mesh is for east-west (service → service)

## Key Concepts
- **North-South Traffic**: Client-to-service traffic that flows "into" the cluster. The gateway handles this. Distinct from east-west (service-to-service) traffic handled by service mesh
- **Cross-Cutting Concerns at the Gateway**: Authentication (JWT verification), rate limiting, TLS termination, request logging, CORS, IP allowlisting/blocklisting, request ID injection
- **Routing**: Path-based routing (`/orders` → orders-service), header-based routing (API version routing), canary routing (5% of traffic to new version)
- **Protocol Translation**: Expose a REST API to clients while communicating with backend via gRPC. The gateway translates protocol, schema, and response format
- **Backend for Frontend (BFF)**: A specialized gateway variant that aggregates multiple backend services into a single API shaped for a specific client (mobile app, web app). Reduces client-side orchestration
- **Gateway vs. Load Balancer**: A load balancer distributes traffic to identical instances. A gateway routes to different services based on path/headers and applies cross-cutting logic
- **Single Point of Failure**: The gateway is on the critical path — it must be highly available, horizontally scalable, and never a bottleneck. Managed gateways (AWS API Gateway) handle this; self-managed (Kong) require HA deployment
- **Avoid Business Logic in the Gateway**: The gateway handles infrastructure concerns. Business logic belongs in services. A gateway that contains routing logic tied to business rules becomes a maintenance liability

## In Practice
Method uses AWS API Gateway for serverless architectures and Kong or Nginx for Kubernetes deployments. Authentication (JWT verification) and rate limiting run at the gateway. Services receive pre-authenticated requests with user identity in injected headers. Routing is path-based. BFF gateways are used for mobile clients with distinct API shape requirements.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — API Gateway Design**: The gateway is the right place for auth, rate limiting, TLS, CORS, and logging — not in every service. It handles north-south traffic; service mesh handles east-west. Keep business logic out of the gateway — routing rules tied to business concepts belong in services. Use BFF pattern for clients with distinct API shape needs. Ensure the gateway is horizontally scalable and monitored — it's on the critical path for all external traffic. → `engineering-knowledge-repository/api-design/api-gateway-design.md`

## Related Entries
- [API Rate Limiting Design](api-rate-limiting-design.md) — rate limiting is enforced at the gateway layer
- [API Security](../security/api-security.md) — authentication and TLS termination live at the gateway
- [Service Discovery](../cloud-patterns/service-discovery.md) — the gateway routes to services via service discovery
- [Microservices](../architectural-styles/microservices.md) — gateways are essential infrastructure for microservices

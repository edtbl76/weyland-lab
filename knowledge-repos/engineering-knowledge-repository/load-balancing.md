---
id: load-balancing
tags: [pattern, infrastructure, network, backend, reliability]
surfaces-at: [application-design, infrastructure-design]
related: [consistent-hashing, horizontal-vs-vertical-scaling, auto-scaling, health-checks, circuit-breaker]
complexity: intermediate
---

# Load Balancing

## What It Is
Distributing incoming network traffic across multiple backend servers to prevent any single server from becoming a bottleneck, ensure high availability, and enable horizontal scaling. A load balancer sits between clients and backend instances, routing each request to a healthy server according to a distribution algorithm. It also performs health checking — removing unhealthy instances from the pool automatically. Load balancing is fundamental infrastructure for any production service that runs multiple instances.

## When to Apply
- Any service running more than one instance
- Achieving high availability — traffic is rerouted when an instance fails
- Horizontal scaling — add instances to handle more load
- Zero-downtime deployments — drain instances before taking them out of rotation

## Key Concepts
- **Layer 4 vs. Layer 7**:
  - *L4 (Transport)*: Routes based on IP/TCP — fast, simple, no HTTP awareness. Used for raw TCP traffic
  - *L7 (Application)*: Routes based on HTTP headers, URL path, cookies — enables path-based routing, sticky sessions, SSL termination, request inspection. AWS ALB, nginx, HAProxy in L7 mode
- **Algorithms**:
  - *Round Robin*: Requests distributed sequentially across instances. Simple; works when requests are similar in cost
  - *Least Connections*: Route to the instance with the fewest active connections. Better for variable-cost requests
  - *IP Hash / Consistent Hashing*: Same client always routes to the same server (session affinity). Required when server-side session state is not externalized
  - *Weighted Round Robin*: Different instances receive different traffic proportions — useful for canary deployments or heterogeneous instance sizes
- **Health Checks**: Load balancers poll backend instances on a health endpoint. Unhealthy instances are removed from the pool; recovered instances are re-added. Define meaningful health checks — not just "port is open" but "application is responding correctly"
- **SSL Termination**: The load balancer handles TLS — decrypts client connections and forwards plain HTTP to backends. Simplifies backend configuration; centralizes certificate management
- **Sticky Sessions (Session Affinity)**: Route all requests from the same client to the same backend — required for stateful applications that store session data in memory. Better architecture: externalize session state to Redis and use a stateless application tier
- **Connection Draining**: Before removing an instance (deployment, scale-down), the load balancer stops sending new connections but allows existing connections to complete. Prevents in-flight requests from being interrupted
- **AWS ALB / NLB**: ALB (Application Load Balancer) — L7, path/host routing, WebSocket support. NLB (Network Load Balancer) — L4, ultra-high throughput, static IP. ALB is the default for HTTP services

## In Practice
Method uses AWS ALB for all HTTP services — L7 routing, SSL termination, and path-based routing. Health checks hit `/health` endpoints with a 5-second timeout and 2-failure threshold. Connection draining is enabled for all target groups. Session state is externalized to Redis — sticky sessions are not used.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Load Balancing**: Use L7 load balancing (ALB) for HTTP services — path-based routing, SSL termination, and WebSocket support are worth the small overhead over L4. Define meaningful health checks, not just port checks — an unhealthy application that accepts TCP connections will receive traffic it can't serve. Externalize session state to avoid sticky sessions — stateless application tiers are easier to scale and deploy. Enable connection draining for all instances before deregistering them — it's the difference between graceful and abrupt request termination. Consistent hashing is for distributed data systems; round-robin or least-connections is correct for stateless HTTP services. → `engineering-knowledge-repository/load-balancing.md`

## Related Entries
- [Consistent Hashing](consistent-hashing.md) — consistent hashing is used in load balancers for session affinity with minimal disruption on topology changes
- [Horizontal vs. Vertical Scaling](horizontal-vs-vertical-scaling.md) — load balancing enables horizontal scaling by distributing traffic across instances
- [Auto Scaling](auto-scaling.md) — auto scaling adds and removes instances; the load balancer distributes traffic across the current pool
- [Health Checks](health-checks.md) — load balancers use health checks to determine instance availability
- [Circuit Breaker](circuit-breaker.md) — circuit breakers in the application layer complement load balancer health checks for dependency failures

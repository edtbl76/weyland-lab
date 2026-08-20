---
id: stateless-architecture
tags: [principle, backend, cloud, distributed-systems]
surfaces-at: [application-design, nfr-requirements, infrastructure-design]
related: [horizontal-vs-vertical-scaling, cloud-native-design, auto-scaling, twelve-factor-app]
complexity: foundational
---

# Stateless Architecture

## What It Is
A design approach where service instances do not store any client session state in local memory between requests. Each request is self-contained — it includes all the information needed to process it. State that must persist (sessions, user data, application state) lives in external systems: databases, caches (Redis), or is carried by the client (JWT). Stateless services are the prerequisite for horizontal scaling — you can add or remove instances at will because no instance holds unique state.

## When to Apply
- Any service that needs to scale horizontally
- Cloud-native services deployed in containers or serverless environments where instances are ephemeral
- Services behind a load balancer where requests may be routed to any instance
- Microservices — statelessness enables independent deployment and scaling

## When Not to Apply
- Stateful workloads by nature: databases, message brokers, stateful streaming processors
- When client-affinity (sticky sessions) is a hard requirement that cannot be redesigned

## Key Concepts
- **Shared Nothing Architecture**: Instances share no in-process state with each other. All shared state lives in external, shared systems
- **Session Externalization**: Move HTTP session state to Redis, Memcached, or a database — any instance can serve any request because session data is externally accessible
- **Twelve-Factor App (Factor VI — Processes)**: "Execute the app as one or more stateless processes. Never store anything in the running process that must persist beyond a single request"
- **Idempotency**: Stateless services often need to be idempotent — the same request can safely be retried without side effects, because any instance may receive the retry
- **JWT for Client-Carried State**: Instead of server-side sessions, authentication state lives in a signed JWT the client presents on every request — the server verifies it without a lookup
- **Load Balancer Compatibility**: Stateless services work with round-robin load balancing. Stateful services require sticky sessions — a fragility and scaling bottleneck
- **Horizontal Scaling**: Because no instance holds unique state, instances can be added or removed elastically. Auto-scaling only works reliably with stateless services

## In Practice
All Method application services are designed stateless by default. HTTP sessions use Redis-backed session stores. Authentication uses JWTs — no server-side session. Kubernetes deployments scale Pods freely because no Pod holds unique state. The only stateful components are the database and cache — which are not horizontally scaled the same way.

## Engineering Knowledge
💡 **Engineering Knowledge — Stateless Architecture**: Stateless services scale horizontally; stateful services don't. Move session state to Redis. Use JWTs for auth — no server-side session lookup required. Store nothing in the running process that must survive beyond a single request (Twelve-Factor Factor VI). Once your services are stateless, load balancers can route freely, auto-scaling works cleanly, and deployments can replace instances without draining connections. Stateful services (databases, caches) are the exception — treat them as the system-of-record, not the application tier. → `engineering-knowledge-repository/architectural-styles/stateless-architecture.md`

## Related Entries
- [Horizontal vs. Vertical Scaling](../performance/horizontal-vs-vertical-scaling.md) — statelessness is the prerequisite for horizontal scaling
- [Cloud-Native Design](../cloud-patterns/cloud-native-design.md) — stateless services are a core cloud-native design principle
- [Auto-Scaling](../cloud-patterns/auto-scaling.md) — auto-scaling requires stateless services to work correctly

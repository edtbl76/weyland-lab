---
id: horizontal-vs-vertical-scaling
tags: [principle, performance, infrastructure]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [caching-strategies, auto-scaling, connection-pooling, stateless-architecture]
complexity: foundational
---

# Horizontal vs. Vertical Scaling

## What It Is
Two fundamental strategies for increasing a system's capacity. **Vertical scaling** (scale up) adds more resources to an existing instance — more CPU, more memory, a bigger VM. **Horizontal scaling** (scale out) adds more instances — more servers, more containers running the same service. The choice between them has architectural implications: horizontal scaling requires stateless services; vertical scaling has hard limits.

## When to Apply
**Vertical Scaling**:
- Single-instance systems that haven't reached the cost ceiling yet
- Databases — vertical scaling is often the first scaling option for relational databases (read replicas and sharding come later)
- Legacy applications that aren't architected for horizontal scaling

**Horizontal Scaling**:
- Stateless services — most modern web services are stateless and horizontally scalable by design
- When traffic is unpredictable and auto-scaling is needed (horizontal scales faster and more granularly)
- When vertical limits are reached or cost-efficiency of horizontal is better

## When Not to Apply
- Horizontal scaling as a substitute for fixing performance problems — adding more instances of a slow service is expensive; profiling and optimization is often more effective
- Vertical scaling as an infinite solution — all cloud instance types have a maximum size; architecture must eventually support horizontal scaling for large scale

## Key Concepts
- **Stateless Services**: Horizontal scaling requires no server-side session state — each request can be handled by any instance. State lives in external stores (databases, caches, Redis sessions).
- **Load Balancer**: The mechanism for distributing traffic across horizontal instances
- **Auto-Scaling**: Dynamically adjusting horizontal instance count based on demand — scale out when CPU/RPS is high, scale in when idle
- **Cost Efficiency**: Horizontal scaling with smaller instances is often more cost-efficient than one very large instance — plus better fault tolerance (no single instance failure takes down the service)
- **Database Scaling**: Databases scale differently — read replicas for read-heavy workloads, sharding for very large datasets, vertical scaling as the first option before distribution complexity

## In Practice
Horizontal scaling of stateless services is the standard architecture for Method cloud-native engagements. AWS ECS/EKS with auto-scaling groups handle horizontal scaling automatically. The key design principle: services must be stateless to scale horizontally. Session state, file uploads, and user-specific state must be externalized.

## Engineering Knowledge
💡 **Engineering Knowledge — Horizontal vs. Vertical Scaling**: Scale up (bigger instance) is simple but has a ceiling and a single point of failure. Scale out (more instances) is more resilient and auto-scalable but requires stateless services. Design your services to be stateless from day one — state in the database, sessions in Redis, files in S3. Then horizontal scaling is trivial to configure. Don't add more instances of a fundamentally slow service — profile and optimize first. → `engineering-knowledge-repository/performance/horizontal-vs-vertical-scaling.md`

## Related Entries
- [Caching Strategies](caching-strategies.md) — caching is often the most cost-effective scaling solution before adding instances
- [Auto-Scaling](../cloud-patterns/auto-scaling.md) — automated horizontal scaling based on demand signals

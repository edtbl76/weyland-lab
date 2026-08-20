---
id: multi-region-deployment
tags: [pattern, infrastructure, reliability]
surfaces-at: [infrastructure-design]
related: [disaster-recovery-patterns, load-balancing, auto-scaling, caching-strategies, infrastructure-as-code]
complexity: advanced
---

# Multi-Region Deployment

## What It Is
Running application and data infrastructure in multiple geographic cloud regions simultaneously to achieve resilience against regional outages, reduce latency for globally distributed users, or meet data residency requirements. Multi-region architectures range from active-passive (one region active, another on standby) to active-active (traffic served from multiple regions concurrently). The primary tradeoff is data consistency — synchronizing state across regions introduces latency, complexity, and eventual consistency challenges. Multi-region is not the first solution for reliability; multi-AZ within a single region handles most failure scenarios.

## When to Apply
- Applications with SLAs requiring < 30 minutes RTO that a single-region failure would violate
- User bases in multiple continents where latency from a single region is unacceptable
- Data residency requirements (GDPR data sovereignty, regulated financial data)
- Business continuity requirements for critical systems (financial services, healthcare, government)

## Key Concepts
- **Single-Region Multi-AZ (First)**: Before considering multi-region, ensure the application is resilient within a single region across multiple Availability Zones. AZ failures are more common than full regional failures. Multi-AZ is significantly simpler and cheaper
- **Active-Passive**: One region (primary) serves all traffic; the standby region is on hot, warm, or cold standby. On regional failure, traffic fails over to the standby region. Simpler data consistency (single write region); failover time depends on standby warmth. Common for disaster recovery use cases
  - *Hot standby*: Standby region is fully running and current. Fast failover (seconds to minutes). Expensive — full duplicate infrastructure
  - *Warm standby*: Scaled-down infrastructure in standby; scales up on failover. Minutes to tens of minutes RTO. Moderate cost
  - *Cold standby*: Infrastructure is provisioned on demand (IaC runbooks). Hours RTO. Lower cost; highest risk
- **Active-Active**: Traffic served from multiple regions simultaneously. Each region handles a portion of users. Database writes must be replicated across regions (or partitioned by user/region). Lowest latency for distributed users; highest complexity. Required for: globally distributed user bases, very high availability SLAs
- **Global Traffic Routing**:
  - *Latency-based routing* (Route 53): DNS routes users to the lowest-latency region
  - *Geolocation routing* (Route 53): Route users to specific regions based on their geographic location (data residency)
  - *Failover routing* (Route 53): Primary/secondary routing with health-check-based automatic failover
  - *Anycast* (Cloudflare, CloudFront): CDN and edge networks route to the nearest healthy PoP
- **Data Replication**:
  - *Relational databases*: Aurora Global Database replicates across regions with < 1 second replication lag. Cross-region read replicas for PostgreSQL/MySQL. Writes go to primary region; reads from local replica
  - *DynamoDB Global Tables*: Multi-region active-active; eventual consistency; last-write-wins conflict resolution
  - *Redis*: ElastiCache Global Datastore provides cross-region active-passive replication
- **CAP Theorem Implications**: Multi-region active-active systems must choose between consistency and availability during network partitions. Most choose availability + eventual consistency (AP systems). Banking and financial transactions typically require consistency (CP) — which limits active-active patterns
- **Data Residency**: Some use cases require user data to stay within a geographic boundary. Route data at the application layer by user region; ensure database writes go to the region-appropriate data store. More complex than latency-based routing

## In Practice
Method uses multi-AZ within a single region as the default reliability posture. Multi-region is implemented only for applications with documented regional resilience requirements. Active-passive with Aurora Global Database is the most common pattern — primary in us-east-1, warm standby in us-west-2, automatic failover via Route 53 health-check-based routing. Infrastructure in both regions is defined as identical Terraform configurations with region-specific parameters.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Multi-Region Deployment**: Multi-region is a last resort, not a default. Start with multi-AZ within one region — it's 10x simpler and handles 99% of failure scenarios. When multi-region is justified, the hardest problem is always data: pick one write region and replicate reads, or pay the price of distributed consistency. Aurora Global Database is the pragmatic answer for PostgreSQL at scale — sub-second cross-region replication with readable replicas in each region. Define your RTO and RPO requirements first; they determine whether hot/warm/cold standby or active-active is the right model. → `engineering-knowledge-repository/multi-region-deployment.md`

## Related Entries
- [Disaster Recovery Patterns](disaster-recovery-patterns.md) — multi-region deployment is an implementation strategy for disaster recovery requirements
- [Load Balancing](load-balancing.md) — global traffic management routes users to the appropriate regional load balancer
- [Auto Scaling](auto-scaling.md) — auto scaling operates within each region; capacity management applies per-region
- [Infrastructure as Code](infrastructure-as-code.md) — multi-region infrastructure is managed as IaC with parameterized region configurations
- [Caching Strategies](caching-strategies.md) — cross-region cache replication reduces origin load in active-active architectures

---
id: capacity-planning
tags: [methodology, reliability, infrastructure, performance]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [load-testing, auto-scaling, horizontal-vs-vertical-scaling, service-level-objectives, site-reliability-engineering]
complexity: intermediate
---

# Capacity Planning

## What It Is
The process of forecasting future resource requirements and ensuring infrastructure is provisioned to handle anticipated load without performance degradation or service failure. Capacity planning answers: how much traffic can the current system handle, how is usage growing, and when will current capacity be exhausted? It prevents two failure modes: under-capacity (service degrades under real load) and over-capacity (excessive infrastructure spend on unused resources). Good capacity planning is data-driven, done ahead of time, and revisited regularly.

## When to Apply
- Before planned traffic events (product launches, marketing campaigns, seasonal spikes)
- When traffic is growing and current headroom is unclear
- When setting SLO targets — understanding capacity constraints informs achievable SLOs
- Quarterly or semi-annually as a regular operational review

## Key Concepts
- **Capacity Metrics**:
  - *Throughput*: Requests per second (RPS) the service can handle before latency degrades
  - *Concurrency*: Number of simultaneous connections or in-flight requests
  - *Resource saturation*: CPU, memory, network bandwidth, database connections, disk I/O at capacity limits
  - *Breaking point*: The RPS at which the service starts dropping requests or failing SLOs
- **Demand Forecasting**: Project future load from current growth trends:
  - Analyze historical traffic patterns — daily/weekly/monthly cycles, year-over-year growth
  - Identify growth rate (linear, exponential, seasonal)
  - Project forward: "at current growth rate, we will exceed current capacity in N weeks"
  - Add multiplier for planned events: "our marketing campaign should drive 5x normal traffic on launch day"
- **Load Testing as Input**: Load tests establish the actual capacity ceiling under controlled conditions. Run load tests that ramp to 2x, 5x, and 10x current production traffic to find the breaking point. Combine with capacity projections to determine when infrastructure changes are needed. See [Load Testing](load-testing.md)
- **Headroom Target**: Maintain spare capacity above normal peak — typically 30-50% headroom. Running at 100% capacity leaves no room for traffic spikes, load test overhead, or gradual growth. Google SRE recommends maintaining N+2 redundancy: the system remains healthy if 2 instances fail simultaneously
- **Auto-Scaling and Capacity Planning**: Auto-scaling reduces but does not eliminate capacity planning. Auto-scaling has limits (max instance count, scale-up latency), and instances take time to start. Capacity planning ensures the auto-scaling configuration is set appropriately for anticipated load. A max instance cap set too low defeats auto-scaling during spikes
- **Database Capacity**: Application servers scale horizontally; databases are harder. Capacity plan databases separately — connections, storage growth, query throughput. Key metrics: connection pool saturation, CPU utilization, IOPS, replication lag. Read replicas and connection pooling extend capacity but have their own limits
- **Capacity Reviews**:
  - Monthly: review current utilization headroom vs. targets
  - Quarterly: review growth trajectory and forecast next quarter's capacity needs
  - Pre-event: review capacity for any planned traffic spike (launch, campaign)
- **Cost vs. Reliability Tradeoff**: More headroom = more cost. Find the right balance based on the cost of an outage vs. the cost of spare capacity. For critical services, 50% headroom is cheap insurance; for internal tools, 10% may be acceptable

## In Practice
Method conducts quarterly capacity reviews for all production services. Utilization metrics (CPU, memory, connection pool saturation) are monitored in Datadog with utilization targets (CPU < 70% at peak). Load tests run monthly to validate capacity headroom. Pre-launch capacity reviews are required for any campaign expecting > 2x normal traffic. Auto-scaling max limits are reviewed quarterly against growth forecasts.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Capacity Planning**: "The service handles current load" is not a capacity plan. Know your ceiling (load test to find it), know your growth rate (trend analysis), and know when you'll hit the ceiling (project forward). Maintain 30-50% headroom at peak — a service running at 95% CPU has no burst capacity and will degrade at the first spike. Auto-scaling helps but needs capacity planning inputs: set min/max instance counts based on your load model, not arbitrarily. Database capacity is the most dangerous blind spot — applications scale horizontally; databases usually don't. → `engineering-knowledge-repository/capacity-planning.md`

## Related Entries
- [Load Testing](load-testing.md) — load tests establish the capacity ceiling that capacity planning is based on
- [Auto Scaling](auto-scaling.md) — auto-scaling is the mechanism for acting on capacity planning decisions dynamically
- [Horizontal vs. Vertical Scaling](horizontal-vs-vertical-scaling.md) — capacity planning informs the scaling strategy decision
- [Service Level Objectives](service-level-objectives.md) — SLO targets are only achievable if capacity is sufficient to meet them
- [Site Reliability Engineering](site-reliability-engineering.md) — capacity planning is a core SRE practice for production reliability

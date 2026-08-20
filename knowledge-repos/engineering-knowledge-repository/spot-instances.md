---
id: spot-instances
tags: [pattern, cost, cloud, infrastructure]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [cloud-cost-optimization, finops, auto-scaling, kubernetes]
complexity: intermediate
---

# Spot / Preemptible Instances

## What It Is
Cloud compute instances offered at steep discounts (60-90% off on-demand pricing) in exchange for the cloud provider being able to reclaim them with short notice (2 minutes for AWS Spot, 30 seconds for GCP Preemptible). Spot instances use spare cloud capacity — when demand rises, the provider reclaims the instance. Workloads running on spot must handle interruption gracefully. Used correctly, spot instances are the highest-leverage cost optimization available for compute-heavy workloads.

## When to Apply
- Batch processing, ML training, data pipelines — work that can be checkpointed and resumed
- Stateless auto-scaling groups — replace on-demand worker instances with spot
- CI/CD build agents — jobs are short-lived and retryable
- Kubernetes worker nodes — use spot node pools for non-critical workloads

## Key Concepts
- **Interruption Handling**: The instance receives a 2-minute warning before termination. Applications must handle this gracefully — checkpoint state, drain in-flight work, deregister from load balancers. Failure to handle interruptions causes data loss and errors
- **Instance Diversification**: Never rely on a single instance type for spot capacity — availability varies by type and AZ. Specify a fleet of compatible instance types; the provider selects from available capacity. AWS Spot Fleet, EC2 Auto Scaling mixed instances policy
- **Availability Zones**: Spread spot requests across multiple AZs — spot capacity varies by AZ. A fleet across 3 AZs and 5 instance types is much more reliable than a single type in one AZ
- **Spot for Stateless Workers**: The canonical use case — auto-scaling groups of stateless application servers behind a load balancer. On interruption, the instance is deregistered and replaced. No data loss; brief reduction in capacity
- **Checkpointing for Batch Jobs**: Long-running batch jobs (ML training, ETL) must save progress periodically. On interruption, resume from the last checkpoint rather than restarting. ML frameworks (PyTorch, TensorFlow) support checkpoint/resume natively
- **Mixed On-Demand and Spot**: Use a base of on-demand instances for minimum capacity, spot for burst. Ensures the service remains available even during spot shortages. AWS recommends 20-30% on-demand base with spot for the remainder
- **Spot Savings Plans / Committed Use**: Combine spot instances with Savings Plans (AWS) or Committed Use Discounts (GCP) for predictable baseline load — spot covers the variable portion
- **Not for Stateful Workloads**: Databases, stateful services, and anything that cannot tolerate sudden termination should run on on-demand or reserved instances. The cost savings don't justify the reliability risk

## In Practice
Method uses spot instances for ML training jobs (PyTorch with checkpointing), CI/CD build agents, and stateless application worker pools. Auto-scaling groups use mixed instances policy with 5+ instance types across 3 AZs. On-demand base covers 20% of minimum capacity. Interruption handlers drain connections and checkpoint state.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Spot Instances**: Spot instances offer the largest cost savings available for compute — 60-90% off on-demand. The requirement is interruption tolerance: your workload must handle a 2-minute shutdown gracefully. Diversify across 5+ instance types and 3 AZs — single-type spot requests fail under capacity pressure. Use mixed on-demand/spot with an on-demand base for production services — never run critical services on 100% spot. Implement interruption handlers: drain connections, checkpoint state, deregister from load balancers. ML training and batch jobs are the best fit; stateful services are the worst. → `engineering-knowledge-repository/spot-instances.md`

## Related Entries
- [Cloud Cost Optimization](cloud-cost-optimization.md) — spot instances are the highest-leverage compute cost optimization
- [FinOps](finops.md) — spot instance strategy is part of the FinOps reserved/spot/on-demand capacity mix
- [Auto Scaling](auto-scaling.md) — auto-scaling groups using mixed instances policy combine on-demand and spot capacity
- [Kubernetes](kubernetes.md) — Kubernetes node pools support spot instances for non-critical workload scheduling

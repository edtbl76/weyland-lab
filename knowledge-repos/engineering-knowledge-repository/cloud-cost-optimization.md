---
id: cloud-cost-optimization
tags: [methodology, cost, cloud]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [auto-scaling, serverless, managed-services-tradeoffs, infrastructure-as-code]
complexity: intermediate
---

# Cloud Cost Optimization

## What It Is
The practice of reducing cloud infrastructure spending without sacrificing performance, reliability, or security. Cloud costs can grow unexpectedly — untagged resources, over-provisioned instances, and unused reserved capacity are common sources of waste. FinOps (Financial Operations) is the organizational practice of shared responsibility for cloud cost management between engineering, finance, and operations.

## When to Apply
- Ongoing operational practice — cloud costs require active management, not one-time optimization
- Before signing reserved instance/savings plan commitments — right-size first
- When cloud spending is growing faster than business growth
- Post-launch review — production workloads often over-provision compared to actual usage

## Key Concepts
- **Right-Sizing**: Match instance size to actual workload requirements. Use AWS Compute Optimizer or similar to identify over-provisioned instances.
- **Reserved Instances / Savings Plans**: Commit to 1-3 year usage in exchange for 40-60% discounts vs. on-demand. Best for stable, predictable workloads.
- **Spot Instances**: Spare compute capacity at 60-90% discount — can be interrupted with 2-minute notice. Suitable for fault-tolerant, stateless workloads.
- **Auto-Scaling**: Right-sizing at runtime — don't provision for peak capacity; scale to demand
- **Storage Tier Optimization**: S3 Intelligent-Tiering, EBS volume type matching, RDS storage autoscaling
- **Tagging Strategy**: Tag all resources with owner, environment, and application — essential for cost attribution and identifying orphaned resources
- **FinOps Tooling**: AWS Cost Explorer, CloudHealth, Infracost (shift-left cost estimation in IaC PRs)
- **Unused Resources**: Idle NAT gateways, unattached EBS volumes, old snapshots, unused Elastic IPs — common low-hanging fruit

## In Practice
Cloud cost optimization is a standing concern in Method infrastructure engagements. Establish tagging standards in Iteration 0. Review costs monthly. Infracost in CI provides cost estimates before infrastructure changes are deployed — shift-left cost visibility. Reserved instance purchases should be made after at least 30 days of production usage data to right-size the commitment.

## Engineering Knowledge
💡 **Engineering Knowledge — Cloud Cost Optimization**: Cloud costs are not set-it-and-forget-it. Tag everything (owner, env, app) so costs are attributable. Right-size first, then buy Reserved Instances — commit after you have 30 days of production data. Auto-scaling eliminates idle over-provisioning. Use Infracost in CI to see cost implications of IaC changes before they merge. Review for orphaned resources monthly — unattached EBS volumes and idle NAT gateways accumulate silently. → `engineering-knowledge-repository/cloud-patterns/cloud-cost-optimization.md`

## Related Entries
- [Auto-Scaling](auto-scaling.md) — auto-scaling eliminates the need to provision for peak capacity at all times
- [Serverless](../architectural-styles/serverless.md) — serverless pay-per-execution can significantly reduce costs for variable workloads
- [Infrastructure as Code](../deployment/infrastructure-as-code.md) — IaC makes cost tracking and optimization changes repeatable

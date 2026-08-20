---
id: finops
tags: [methodology, cost, cloud, team-practices]
surfaces-at: [nfr-requirements, application-design]
related: [cloud-cost-optimization, managed-services-tradeoffs, infrastructure-as-code, auto-scaling]
complexity: intermediate
---

# FinOps

## What It Is
A cultural and organizational practice that brings financial accountability to cloud spending by creating shared ownership between engineering, finance, and business teams. FinOps is not just cost cutting — it is the discipline of making deliberate cost-value tradeoffs: understanding what you are spending, why, whether it delivers value, and who is responsible for it. As cloud bills scale with product growth, unmanaged cloud spend becomes a material business risk.

## When to Apply
- Any organization with significant and growing cloud spend
- When cloud costs are not visible to the teams generating them
- Before a product scales — reactive cost management is more expensive than proactive
- When business units or products need cost accountability

## Key Concepts
- **Tagging Strategy**: Every cloud resource is tagged with owner (team), product, environment (prod/staging/dev), and cost center. Tags are the foundation of all cost attribution — without consistent tagging, you cannot allocate costs. Enforce tags via IaC and cloud policy (AWS SCPs, Azure Policy)
- **Showback**: Report cloud costs back to the teams generating them — visibility without financial accountability. First step: teams see what they cost
- **Chargeback**: Allocate cloud costs directly to the business unit or product budget responsible. Stronger accountability; requires mature tagging and organizational buy-in
- **Unit Economics**: Express cloud costs in business terms — cost per user, cost per transaction, cost per API call. Unit economics make cost conversations meaningful to non-technical stakeholders and expose efficiency regressions
- **Cost Anomaly Detection**: Alert on unexpected spend spikes before they become large bills. AWS Cost Anomaly Detection, cloud provider budgets with alerts. Act on anomalies within hours, not at month-end
- **FinOps Lifecycle**: Inform (visibility and allocation) → Optimize (right-sizing, reserved capacity, waste elimination) → Operate (governance, accountability, continuous improvement)
- **Reserved Instances / Savings Plans**: Committing to 1 or 3-year usage in exchange for 30-60% discounts. FinOps governs the commitment strategy — balance savings against flexibility. Analyze usage patterns before committing
- **Cloud Cost Tools**: AWS Cost Explorer, AWS Cost and Usage Report (CUR), GCP Billing, Azure Cost Management. Third-party: Cloudability, CloudHealth, Infracost (cost estimation in CI/CD)
- **Engineering Ownership**: Engineers make the architectural decisions that drive costs. FinOps succeeds when engineers have cost visibility in their workflow — not just finance teams reviewing bills monthly

## In Practice
Method establishes tagging standards at project inception and enforces them via IaC. Cost dashboards per team are set up in the first sprint. Unit economics are defined alongside functional metrics for any product feature. Reserved Instance coverage is reviewed quarterly. Cost anomaly alerts route to the team Slack channel, not just a finance inbox.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — FinOps**: Start with tagging — you cannot manage what you cannot attribute. Every resource gets team, product, environment, and cost center tags enforced at the IaC level. Set up cost alerts before you need them — month-end surprises are avoidable. Express costs in unit economics (cost per user, per transaction) to make engineering cost decisions meaningful to the business. Showback first, chargeback later — visibility creates accountability before you need budget transfers. Engineers own cloud costs; FinOps gives them the visibility to act on that ownership. → `engineering-knowledge-repository/finops.md`

## Related Entries
- [Cloud Cost Optimization](cloud-cost-optimization.md) — technical tactics for reducing cloud spend within the FinOps framework
- [Managed Services Tradeoffs](managed-services-tradeoffs.md) — build vs. buy decisions have direct FinOps cost implications
- [Infrastructure as Code](infrastructure-as-code.md) — IaC enforces tagging standards and enables cost estimation before deployment
- [Auto Scaling](auto-scaling.md) — auto scaling is a key FinOps optimization for matching spend to actual demand

---
id: blue-green-deployment
tags: [pattern, deployment, reliability]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [canary-deployment, feature-flags, strangler-fig]
complexity: intermediate
---

# Blue-Green Deployment

## What It Is
A deployment strategy that maintains two identical production environments — "Blue" (current live) and "Green" (new version) — and switches traffic between them atomically. The new version is deployed and verified on the inactive environment; when ready, traffic is redirected from Blue to Green (or vice versa) in a single switch. If problems emerge, rolling back is as fast as switching traffic back. Enables zero-downtime deployments and instant rollback.

## When to Apply
- Production systems where downtime is unacceptable during deployments
- Systems requiring instant rollback capability without re-deploying old code
- Teams that want to verify the new version in a production-identical environment before serving live traffic
- Deployments of significant changes where confidence needs to be built before full traffic exposure

## When Not to Apply
- Resource-constrained environments where running two identical production stacks is cost-prohibitive
- Systems with stateful components (persistent connections, in-flight transactions) that can't cleanly cut over
- When schema migrations are incompatible with running two versions simultaneously — requires careful migration sequencing
- Simple services where rolling deployments (Kubernetes default) are sufficient

## Key Concepts
- **Two Environments**: Blue and Green are identical infrastructure. One is live; one is staged with the new version.
- **Traffic Switch**: A load balancer, DNS change, or API Gateway rule redirects all traffic from the inactive environment to the active one
- **Verification Window**: Time between deploying to the inactive environment and switching traffic — used for smoke tests, health checks, and pre-production validation
- **Instant Rollback**: Reverse the traffic switch to roll back — no redeployment required
- **Database Migrations**: The hardest part. If Green requires a schema change, Blue and Green must be able to use the same database simultaneously. Use backwards-compatible migrations (expand/contract pattern).
- **Warm-Up**: The new environment may need time to initialize caches or connection pools before receiving traffic

## In Practice
Blue-green deployment is a standard release strategy in Method infrastructure engagements for services with SLA uptime requirements. AWS CodeDeploy, Spinnaker, and Kubernetes blue-green controllers automate the infrastructure switch. The most common complication is database schema migrations — incompatible migrations block zero-downtime blue-green. The expand/contract migration pattern (add columns before removing old ones) is the solution.

## Engineering Knowledge
💡 **Engineering Knowledge — Blue-Green Deployment**: Deploy the new version to an idle environment, verify it, then flip the traffic switch. Zero downtime, instant rollback — just flip back. The hard part is database migrations: both environments share the same database, so migrations must be backwards-compatible (expand/contract). Blue-green is more expensive than rolling deploys but indispensable when downtime or slow rollbacks are unacceptable. → `engineering-knowledge-repository/deployment/blue-green-deployment.md`

## Related Entries
- [Canary Deployment](canary-deployment.md) — gradual traffic migration as an alternative to instant switch
- [Feature Flags](feature-flags.md) — decouple feature activation from deployment without environment switching
- [Strangler Fig](../infrastructure/strangler-fig.md) — traffic switching is a shared mechanism with Strangler Fig migrations

---
id: rolling-deployment
tags: [pattern, deployment, reliability]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [blue-green-deployment, canary-deployment, immutable-infrastructure]
complexity: foundational
---

# Rolling Deployment

## What It Is
A deployment strategy that gradually replaces instances of the previous version of an application with the new version — one at a time or in small batches. At any point during the rollout, some instances run the old version and some run the new version. Kubernetes' default deployment strategy is rolling update. Provides zero-downtime deployment without requiring two full environment copies (unlike Blue-Green).

## When to Apply
- The default deployment strategy for most stateless services — Kubernetes handles it automatically
- When you need zero-downtime deployments without the cost of maintaining a duplicate environment
- Services where running two versions simultaneously is safe — backward-compatible API changes

## When Not to Apply
- When running two versions simultaneously is unsafe — incompatible database schema changes, breaking API changes
- When instant rollback is required — rolling rollback is slower than a Blue-Green traffic switch
- When you need to validate the new version on a production-equivalent environment before any real traffic hits it (use Blue-Green instead)

## Key Concepts
- **Rollout Pace**: Controlled by `maxUnavailable` and `maxSurge` in Kubernetes — how many instances can be down or over-capacity during the rollout
- **Readiness Probe**: Kubernetes waits for the new instance to pass its readiness probe before routing traffic and replacing the next old instance
- **Automatic Rollback**: Kubernetes halts a rolling deployment if new instances fail to pass readiness checks — but you must configure this
- **Version Coexistence**: During the rollout, old and new code run simultaneously — API compatibility between versions must be maintained
- **Deployment Pause**: Rolling deployments can be paused mid-rollout for manual inspection before proceeding

## In Practice
Rolling deployment is the baseline Kubernetes deployment strategy and the starting point for most Method Kubernetes engagements. Configure readiness and liveness probes — without them, Kubernetes routes traffic to instances that aren't ready yet. For more sophisticated release control (gradual percentage-based rollout, automated analysis), evolve to Canary or Blue-Green as needs require.

## Engineering Knowledge
💡 **Engineering Knowledge — Rolling Deployment**: Kubernetes' default — replace old instances with new ones gradually. Zero downtime, no duplicate environment cost. The key: configure readiness probes so Kubernetes waits for new instances to be ready before pulling old ones. Both versions run simultaneously during rollout — ensure backward-compatible API changes. For instant rollback or pre-production validation, use Blue-Green instead. → `engineering-knowledge-repository/deployment/rolling-deployment.md`

## Related Entries
- [Blue-Green Deployment](blue-green-deployment.md) — instant switch alternative to gradual rolling
- [Canary Deployment](canary-deployment.md) — percentage-based gradual rollout with monitoring

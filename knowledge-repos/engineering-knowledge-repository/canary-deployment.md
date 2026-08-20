---
id: canary-deployment
tags: [pattern, deployment, reliability]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [blue-green-deployment, feature-flags, circuit-breaker]
complexity: intermediate
---

# Canary Deployment

## What It Is
A deployment strategy where a new version is released to a small subset of users or traffic (the "canary") before rolling it out to everyone. Traffic is gradually shifted from the old version to the new — for example, 1% → 5% → 25% → 100% — with monitoring at each stage. If metrics degrade at any stage, the rollout is halted and traffic is shifted back. Named after the "canary in a coal mine" — the canary detects danger early before it affects everyone.

## When to Apply
- Deployments of significant changes where production behavior is uncertain and you want real user signal before full exposure
- High-traffic systems where even a small percentage of traffic provides statistically meaningful feedback
- Systems with robust observability — canary deployments require metrics, error rates, and latency data to make the promotion/rollback decision
- When the blast radius of a bad deployment must be minimized

## When Not to Apply
- Low-traffic services where a 1% canary receives zero real requests
- Systems without sufficient observability to detect whether the canary is healthy
- Changes that cannot run two versions simultaneously (breaking protocol changes, incompatible database schemas)
- Very simple changes where the deployment risk is low and full blue-green or rolling deploy is sufficient

## Key Concepts
- **Canary Population**: The subset receiving the new version — can be percentage-based, user-segment-based (internal users, beta users), or geographic
- **Traffic Splitting**: Load balancer or service mesh routes a percentage of traffic to canary instances. Tools: Nginx, Istio, AWS App Mesh, Argo Rollouts.
- **Automated Analysis**: Compare metrics (error rate, latency p99, business metrics) between canary and stable versions — automated promotion or rollback based on thresholds
- **Promotion**: When the canary is healthy at the current traffic level, advance to the next stage
- **Rollback**: Shift all traffic back to the stable version if canary metrics degrade
- **Blast Radius**: At any point, the maximum number of affected users is capped by the current canary traffic percentage

## In Practice
Canary deployment is the preferred progressive delivery strategy for high-stakes releases in Method engagements. It requires mature observability — without dashboards and alerting, you can't make informed promotion decisions. Argo Rollouts (Kubernetes) provides automated canary analysis with Prometheus or Datadog integration. For most teams, a manual canary starting at 5% with a monitoring window before advancing is sufficient.

## Engineering Knowledge
💡 **Engineering Knowledge — Canary Deployment**: Don't deploy to everyone at once. Send 1-5% of traffic to the new version, watch your metrics, and promote gradually. If error rates or latency spike, roll back before the blast radius grows. Canary requires observability — you need metrics to know if the canary is healthy. For automated analysis, Argo Rollouts integrates canary progression with Prometheus thresholds. → `engineering-knowledge-repository/deployment/canary-deployment.md`

## Related Entries
- [Blue-Green Deployment](blue-green-deployment.md) — instant full switch vs. gradual canary traffic migration
- [Feature Flags](feature-flags.md) — canary by user segment using flags rather than traffic splitting
- [Circuit Breaker](../infrastructure/circuit-breaker.md) — circuit breakers protect services when canary issues cascade

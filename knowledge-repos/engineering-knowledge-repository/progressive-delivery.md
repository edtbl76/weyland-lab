---
id: progressive-delivery
tags: [methodology, deployment]
surfaces-at: [application-design]
related: [feature-flags, canary-deployment, blue-green-deployment, a-b-testing, deployment-gates, continuous-delivery]
complexity: intermediate
---

# Progressive Delivery

## What It Is
An umbrella term for deployment and release techniques that expose new features to progressively larger audiences, gating expansion on measured outcomes rather than calendar schedules. Progressive delivery encompasses feature flags, canary deployments, A/B testing, and ring-based deployments — techniques that decouple code deployment (when code reaches production infrastructure) from feature release (when users see the new behavior). Coined by James Governor of RedMonk, progressive delivery is the evolution of continuous delivery toward risk-controlled, data-driven releases where "done" is not a binary state but a gradient from 0% to 100% exposure.

## When to Apply
- New features with uncertain user impact where early feedback is valuable
- High-risk deployments (database migrations, performance-sensitive changes, payment flows)
- When business teams need control over when features are visible without engineering involvement
- Multi-segment user populations where different groups need different rollout timing
- Any organization moving toward trunk-based development and continuous deployment

## Key Concepts
- **Deployment vs. Release**: Progressive delivery makes this distinction explicit. Code is deployed continuously; features are released progressively. A canary deployment is 5% of traffic; a feature flag is 0% until the business decides to release. Both are separate from "code is in production"
- **Techniques**:
  - *Feature Flags*: Toggle features on/off per user segment, region, or percentage. The most flexible progressive delivery mechanism
  - *Canary Deployments*: Route a percentage of traffic to the new version; measure error rates and latency; expand or rollback based on metrics
  - *Ring Deployments*: Release in ordered rings — internal users → beta users → 10% → 50% → 100%. Each ring validates before the next opens
  - *A/B Testing*: Randomly assign users to variants; measure business outcomes (conversion, engagement) to decide which variant wins
  - *Dark Launches*: Execute new code paths in production but suppress user-visible output; measure performance and correctness before exposing
- **Expansion Gates**: Each progression step requires passing gates — error rate below threshold, latency within SLO, no critical alerts. Gates can be manual (engineer or product manager reviews metrics and clicks "expand") or automated (deployment pipeline expands automatically when metrics pass)
- **Observability Requirement**: Progressive delivery is only as good as the observability informing expansion decisions. Without metric-gated rollouts, progressive delivery is just delayed deployment. Key metrics: error rate, P95 latency, business conversion metrics per variant
- **Rollout Strategy**: Define the rollout plan before launch: "1% → 10% → 25% → 50% → 100% with 24-hour hold at each stage." Document what metrics would trigger a rollback at each stage
- **Feature Flag Lifecycle**: Progressive delivery requires feature flag discipline — flags used for progressive rollout should be removed once rollout is complete. Accumulated flags become maintenance debt. See Feature Flag Lifecycle practices
- **Tooling**: LaunchDarkly, Unleash, Flagsmith for feature flags; Argo Rollouts, Flagger for canary orchestration in Kubernetes; Split.io for experimentation-focused progressive delivery

## In Practice
Method uses progressive delivery for all significant feature launches on client applications. Feature flags control user exposure; canary deployments control traffic routing for infrastructure-level changes. Rollout plans are written as part of the release plan, including expansion gates and rollback triggers. Automated gates check error rate and latency before each ring expansion. Feature flags used for rollout are removed within 2 sprints of reaching 100%.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Progressive Delivery**: Progressive delivery shifts the risk calculus of releasing software — instead of a binary launch event, you have a controlled gradient of exposure with an escape valve at every step. The prerequisite is observability: if you can't measure error rates and latency per variant in real time, you're flying blind. Define your expansion gates and rollback criteria before the rollout begins, not in the middle of an incident. Progressive delivery without feature flag cleanup creates long-term maintenance debt — treat flag removal as part of the delivery definition. → `engineering-knowledge-repository/progressive-delivery.md`

## Related Entries
- [Feature Flags](feature-flags.md) — the primary mechanism for controlling feature exposure in progressive delivery
- [Canary Deployment](canary-deployment.md) — traffic-splitting deployment strategy; one component of progressive delivery
- [Blue-Green Deployment](blue-green-deployment.md) — complementary deployment strategy for zero-downtime releases
- [A/B Testing](a-b-testing.md) — experimentation component of progressive delivery for measuring user impact
- [Deployment Gates](deployment-gates.md) — automated metric gates that control expansion between progressive delivery stages
- [Continuous Delivery](continuous-delivery.md) — progressive delivery extends continuous delivery with risk-controlled release practices

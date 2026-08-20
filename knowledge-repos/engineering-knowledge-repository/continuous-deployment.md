---
id: continuous-deployment
tags: [methodology, deployment]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [continuous-delivery, continuous-integration, feature-flags, canary-deployment, blue-green-deployment]
complexity: intermediate
---

# Continuous Deployment

## What It Is
The practice of automatically deploying every change that passes the full automated test suite to production — no human approval gate. The pipeline is the quality gate. Continuous Deployment is the full automation of Continuous Delivery: the decision to deploy is made by the pipeline, not by a person. Companies like Etsy, Amazon, and Flickr pioneered this approach.

## When to Apply
- When automated test coverage and pipeline confidence are high enough to trust automated deployment
- When deployment frequency goals require eliminating manual approval latency
- When deploys are small, frequent, and routine enough that manual review of each one adds no value
- Feature-flagged systems where code can be deployed without activating features

## When Not to Apply
- Systems with regulatory requirements for explicit human sign-off before production changes
- When test coverage and pipeline confidence are insufficient — automating a bad pipeline causes automated production incidents
- High-risk systems where a bad deploy requires complex remediation — start with CD (human trigger) before removing the gate

## Key Concepts
- **Zero-Touch Deploy**: Every passing build automatically reaches production — no manual trigger
- **Pipeline as the Quality Gate**: The pipeline replaces human review of deployments — its coverage must be trusted
- **Mean Time to Recovery (MTTR)**: With automated deployment, MTTR becomes the key safety metric — if something goes wrong, how fast can it be detected and reverted?
- **Progressive Delivery**: Continuous Deployment often pairs with canary deployment or feature flags — deploy automatically, but release gradually
- **Automated Rollback**: When post-deployment monitoring detects regressions, automated rollback returns to the previous version without human intervention
- **Deployment Frequency**: Continuous Deployment can yield 10-50+ deployments per day for large teams

## In Practice
Pure Continuous Deployment is the aspiration for mature engineering organizations. In Method engagements, the path is: CI → Continuous Delivery (human-triggered production deploy) → Continuous Deployment (automated production deploy). Most clients start at Continuous Delivery and progress toward Continuous Deployment as pipeline confidence and observability mature.

## Engineering Knowledge
💡 **Engineering Knowledge — Continuous Deployment**: No human approval gate — every passing build goes straight to production. The pipeline is your quality gate. Requires high pipeline confidence (comprehensive automated tests), good observability (detect regressions immediately), and fast rollback capability. Don't jump straight here — build Continuous Delivery first, then remove the final manual gate once confidence is established. Feature flags let you deploy safely without activating risky changes. → `engineering-knowledge-repository/deployment/continuous-deployment.md`

## Related Entries
- [Continuous Delivery](continuous-delivery.md) — the step before full automation
- [Canary Deployment](canary-deployment.md) — continuous deployment + canary release = automated, progressive rollout
- [Feature Flags](feature-flags.md) — feature flags make continuous deployment safe for incomplete features

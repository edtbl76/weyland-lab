---
id: continuous-delivery
tags: [methodology, deployment]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [continuous-integration, continuous-deployment, blue-green-deployment, feature-flags, four-key-metrics]
complexity: intermediate
---

# Continuous Delivery (CD)

## What It Is
A software engineering practice where code is kept in a continuously releasable state. Every change that passes automated tests can be deployed to production at any time, by any authorized person, with a single command or button press. CD is the practice; the act of deploying may still be triggered manually. Continuous Delivery is the prerequisite for Continuous Deployment (where every passing build deploys automatically).

## When to Apply
- Teams that want to reduce lead time from code commit to production value
- Systems where long release cycles create risk (large, infrequent releases are riskier than small, frequent ones)
- Reducing the "fear of deployment" by making every deployment a small, routine event
- As an organizational improvement goal — CD is a capability to build toward, not a switch to flip

## When Not to Apply
- Before Continuous Integration is established — CD requires CI as its foundation
- Systems with regulatory, compliance, or contractual approval gates that cannot be automated — adapt the pipeline to include required approvals as pipeline stages
- When the team doesn't have adequate test coverage to trust that automated tests catch regressions

## Key Concepts
- **Deployment Pipeline**: The automated sequence of stages (build → unit test → integration test → staging deploy → acceptance test → production deploy) that every change traverses
- **Release Candidate**: Every build artifact that passes the full pipeline is a release candidate — production-deployable at any point
- **One-Click Deploy**: The triggering mechanism for CD — a human decision, automated execution
- **Continuous Deployment**: The extension of CD where every passing build deploys automatically (no human gate)
- **Pipeline Stages**: Each stage increases confidence; earlier stages are fast, later stages are thorough
- **Production Parity**: Staging and production environments should be as identical as possible — differences cause "works in staging, breaks in prod" failures

## In Practice
Continuous Delivery is the gold standard for Method engineering engagements. Lead time (commit to production) is a DORA metric, and CD directly reduces it. The organizational change is often harder than the technical implementation — approval cultures and manual release processes resist automation. The argument: the current process isn't safer, it's just slower. Small frequent releases are less risky than large infrequent ones.

## Engineering Knowledge
💡 **Engineering Knowledge — Continuous Delivery**: CD means your code is always ready to ship. Every change that passes the pipeline can be deployed to production today, by anyone, without a release ceremony. The value: small frequent releases are dramatically less risky than large batched ones. Build the pipeline first (CI → staging deploy → automated acceptance tests → prod), then fight the cultural battle for removing manual release gates. Lead time drops; confidence rises. → `engineering-knowledge-repository/deployment/continuous-delivery.md`

## Related Entries
- [Continuous Integration](continuous-integration.md) — CI is the prerequisite for CD
- [Continuous Deployment](continuous-deployment.md) — CD with an automated production deploy gate removed
- [Four Key Metrics](../architectural-philosophy/four-key-metrics.md) — CD directly improves deployment frequency and lead time
- [Feature Flags](feature-flags.md) — feature flags decouple deployment from release, enabling CD on incomplete features

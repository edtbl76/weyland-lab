---
id: feature-flags
tags: [pattern, deployment, backend]
surfaces-at: [functional-design, infrastructure-design, nfr-requirements]
related: [canary-deployment, blue-green-deployment, twelve-factor-app]
complexity: foundational
---

# Feature Flags

## What It Is
A technique for controlling feature activation independently from code deployment. A feature flag (also called a feature toggle) wraps a code path in a conditional that can be turned on or off at runtime without redeploying. Flags are stored in configuration or a feature flag service (LaunchDarkly, Flagsmith, AWS AppConfig) and evaluated at request time. This decouples the act of deploying code from the act of releasing a feature.

## When to Apply
- Trunk-based development — merge incomplete features to main behind a flag, avoiding long-lived branches
- Progressive rollouts — release to internal users, then beta users, then everyone, using the same deployed code
- A/B testing and experimentation — split users into control and treatment groups
- Kill switches — disable a misbehaving feature in production without a hotfix deployment
- Canary-by-user-segment — route specific users or tenants to new behavior

## When Not to Apply
- Flags that are never cleaned up — feature flags are technical debt; every flag needs a removal plan
- Using flags to manage long-term configuration (that's a config system problem)
- Complex flag interdependencies — tangled flag logic is hard to reason about and test
- Teams without a flag management system — spreadsheet-tracked flags become unmaintainable quickly

## Key Concepts
- **Release Toggle**: Enables trunk-based development — deploy dark, activate when ready
- **Experiment Toggle**: A/B tests — different user segments get different behavior
- **Ops Toggle**: Kill switch for production issues — operational control without redeployment
- **Permission Toggle**: Gates features by user role or plan (e.g., premium features)
- **Flag Lifetime**: Every flag must have a defined removal date. Flags accumulate and create combinatorial test complexity.
- **Flag as Code**: Flag evaluation logic should be treated as testable code — test both flag-on and flag-off paths
- **LaunchDarkly / Flagsmith / Unleash**: Dedicated feature flag management platforms with SDKs, targeting rules, audit logs, and gradual rollout controls

## In Practice
Feature flags are standard infrastructure in Method engagements where continuous delivery is practiced. The discipline is flag hygiene: every flag needs an owner, a purpose, and a removal ticket. Flags used for experimentation should integrate with analytics to measure outcomes. The twelve-factor app principle of config in the environment applies — flag values are configuration, not code.

## Engineering Knowledge
💡 **Engineering Knowledge — Feature Flags**: Decouple deployment from release. Ship code dark behind a flag; activate when ready. Use flags for trunk-based development (no long-lived branches), progressive rollouts, A/B experiments, and production kill switches. The discipline is cleanup: every flag is technical debt with an expiry date. Use a flag management platform (LaunchDarkly, Flagsmith) for production systems — spreadsheets don't scale. → `engineering-knowledge-repository/deployment/feature-flags.md`

## Related Entries
- [Canary Deployment](canary-deployment.md) — canary by traffic percentage; feature flags enable canary by user segment
- [Blue-Green Deployment](blue-green-deployment.md) — flags eliminate the need for environment switching for many release scenarios
- [Twelve-Factor App](../architectural-philosophy/twelve-factor-app.md) — flags are config, not code

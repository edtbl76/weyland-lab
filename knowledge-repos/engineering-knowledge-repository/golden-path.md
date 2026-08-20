---
id: golden-path
tags: [platform, developer-experience, team-practices]
surfaces-at: [application-design, infrastructure-design]
related: [internal-developer-platform, internal-developer-portal, team-topologies, trunk-based-development, continuous-delivery]
complexity: intermediate
---

# Golden Path

## What It Is
An opinionated, well-maintained default path through an organization's toolchain and platform that enables engineers to build, test, and deploy software with minimal friction and maximum standardization. Coined and popularized by Spotify, the Golden Path is the set of tools, workflows, and conventions the platform team fully supports and recommends — not as a mandate, but as the lowest-resistance route to production. A team that follows the Golden Path gets CI/CD pipelines, test frameworks, observability instrumentation, security scanning, secrets management, and deployment automation configured and working by default. Teams can deviate, but deviation means leaving the supported path and accepting responsibility for what the platform would have provided. The Golden Path is the primary value delivery mechanism of an Internal Developer Platform.

## When to Apply
- When designing a platform team's self-service offering — define the Golden Path before building the tooling
- When engineering organizations have high variance in how teams build, test, and deploy — the Golden Path is the convergence mechanism
- During modernization engagements where the target state includes consistent engineering practices across teams
- When cognitive load assessments reveal that teams spend time solving the same infrastructure problems independently
- When onboarding new engineers takes weeks because there is no standard way to get from zero to production

## When Not to Apply
- Organizations with fewer than 3-4 teams — informal conventions may be sufficient; a formal Golden Path adds overhead before there is enough pattern to codify
- As a mandate in organizations with high team autonomy culture — the Golden Path's power is in being attractive, not required. Enforcing it as a requirement without investment in quality will produce workarounds

## Key Concepts
- **Opinionated Default, Not Mandate**: The Golden Path works when it is faster and better than the alternatives, not because teams are required to use it. Spotify's formulation: "It should be so good that teams *want* to follow it." Platform teams that mandate the path without making it excellent create shadow IT, not standardization.
- **What the Golden Path Covers**: Typically — repository structure and scaffolding, CI/CD pipeline configuration, test framework setup, observability instrumentation (traces, metrics, logs wired by default), secrets management, container build and registry, deployment to target environment, and service registration. Each element is pre-configured; teams fill in the application-specific parts.
- **Scaffolding as Entry Point**: The Golden Path usually starts with a scaffold — a "create new service" command or portal workflow that generates a repository matching the path's conventions. The scaffold is the moment of standardization; everything built on it inherits path compliance.
- **Deviation and Its Cost**: Teams that deviate from the Golden Path must maintain what they deviate from. The platform team explicitly does not support off-path choices. This is not punitive — it is a resource constraint. The cost of deviation should be visible and documented so teams make informed choices.
- **Living Artifact**: The Golden Path must evolve with the platform. A frozen path becomes a legacy path — teams will deviate not because they want to but because the path no longer works. Platform teams maintain the path as a product: versioned, documented, with deprecation cycles for breaking changes.
- **Golden Path vs. Guardrails**: The Golden Path is the recommended route; guardrails are enforced constraints (e.g., secrets may never be stored in environment variables — this is enforced). A mature platform has both: guardrails for the highest-risk decisions and a Golden Path for everything else.
- **Measurable Adoption**: Golden Path adoption is a platform KPI. Metrics: percentage of services on-path, time from scaffold to first production deployment, reduction in "how do I deploy?" support requests. Low adoption signals the path is not competitive with the alternatives.

## In Practice
In Method platform engagements, defining the Golden Path is typically the first design artifact — it establishes the scope of what the platform team commits to supporting. The path is documented as a single page: what it covers, what tools it uses, how to get on it (scaffold), and how to get help when on it. Scaffolding is implemented as a Backstage Software Template or a CLI command (`method-create-service`). The first iteration of the path covers CI/CD and deployment; observability and security scanning are added in subsequent iterations as they become reliable enough to include by default.

## Engineering Knowledge
💡 **Engineering Knowledge — Golden Path**: Define your Golden Path before building your platform. It forces the platform team to answer: "What does a team get when they do things our way?" The answer to that question is your product. A good Golden Path gives teams CI/CD, observability, security scanning, and environment provisioning automatically — not as things to configure, but as things that are already there. Make it faster to follow the path than to build your own, and adoption takes care of itself. → `engineering-knowledge-repository/golden-path.md`

## Related Entries
- [Internal Developer Platform](internal-developer-platform.md) — the IDP is the platform; the Golden Path is the IDP's primary user-facing contract
- [Internal Developer Portal](internal-developer-portal.md) — the portal is often the entry point to the Golden Path via scaffolding templates
- [Team Topologies](team-topologies.md) — platform teams define and maintain the Golden Path; stream-aligned teams consume it
- [Trunk-Based Development](trunk-based-development.md) — trunk-based development is typically part of the Golden Path's branching convention
- [Continuous Delivery](continuous-delivery.md) — a Golden Path that does not include CD is not a complete path to production

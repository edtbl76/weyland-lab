---
id: internal-developer-platform
tags: [platform, developer-experience, team-practices, infrastructure]
surfaces-at: [application-design, infrastructure-design]
related: [internal-developer-portal, golden-path, team-topologies, twelve-factor-app, gitops]
complexity: advanced
---

# Internal Developer Platform

## What It Is
The collection of tools, services, APIs, and automated workflows that a platform team builds and maintains to enable stream-aligned teams to self-serve their infrastructure, deployment, and operational needs — without requiring direct coordination with platform specialists. The Internal Developer Platform (IDP) is the *capability*; the Internal Developer Portal is the *discovery interface* for that capability. An IDP typically includes: self-service environment provisioning, CI/CD pipeline templates, secrets management, container orchestration, observability instrumentation, security scanning, and networking configuration. The goal is to reduce the cognitive load of stream-aligned teams by packaging infrastructure complexity into a product-grade internal API. Distinguished from the Internal Developer Portal (also abbreviated IDP) — the platform is the backend; the portal is the frontend.

## When to Apply
- When stream-aligned teams spend significant time on infrastructure tasks that are not their core domain
- Platform team engagements where the goal is to improve developer self-service and reduce time to production
- Organizations with repeating "how do I deploy X?" or "how do I get Y provisioned?" friction across teams
- When cognitive load assessments (per Team Topologies) show infrastructure burden as a primary bottleneck
- Modernization engagements where the target architecture requires each team to own its deployment lifecycle

## When Not to Apply
- Small organizations (fewer than 3-4 stream-aligned teams) where the overhead of maintaining a platform exceeds its benefit — shared scripts and conventions may suffice
- Early-stage products where infrastructure needs are not yet stable enough to productize — platforming too early locks in bad abstractions

## Key Concepts
- **Platform as a Product**: The platform team treats stream-aligned teams as customers. This means user research, documented APIs, SLAs, versioned releases, and feedback loops — not just internal tooling. The platform team measures success by stream-aligned team velocity, not platform team output.
- **Self-Service Surface**: The defining characteristic. Stream-aligned teams should be able to create environments, deploy services, view logs, and manage configuration without filing tickets or waiting for platform team intervention. The self-service surface is usually exposed through the Developer Portal and platform CLIs.
- **Golden Path**: The IDP's primary value delivery mechanism — an opinionated, well-maintained default path through the platform. Teams that follow the Golden Path get CI/CD, observability, security scanning, and networking configured automatically. The platform team's job is to make the Golden Path attractive enough that deviation requires active justification.
- **Paved Road vs. Guardrails**: The IDP can either mandate standards (guardrails — deviation is prevented) or recommend them (paved road — deviation is allowed but unsupported). Most mature platforms use paved roads for most decisions and guardrails for only the highest-risk ones (e.g., secrets management, network egress).
- **Platform Contracts**: The API boundary between the platform and stream-aligned teams. Stable contracts allow the platform team to evolve the underlying implementation without breaking teams. Contract changes require versioning and migration paths — the platform team is a service provider.
- **Cognitive Load Reduction**: The IDP's design goal, per Team Topologies. Every capability the platform absorbs is cognitive load removed from stream-aligned teams. Design decisions (what to absorb vs. what to expose) are cognitive load decisions, not just technical ones.
- **Adoption Flywheel**: Platform adoption depends on the Golden Path being faster than rolling your own. If teams bypass the platform, the root cause is almost always that the platform's self-service is slower, less reliable, or less flexible than the team's workaround. Platform teams that treat adoption as a success metric build differently than those that treat it as a mandate.

## In Practice
Method platform engagements typically begin with a cognitive load assessment — which infrastructure concerns are consuming stream-aligned team time — before designing the platform surface. The platform MVP is rarely a portal; it is usually a CI/CD pipeline template and an environment provisioning API. The portal comes later when there is enough capability to discover. Tool stack: Kubernetes (orchestration), Terraform/Pulumi (provisioning), GitHub Actions or Tekton (CI/CD), Vault (secrets), Datadog or OpenTelemetry (observability), Backstage (portal). The key design decision is where to draw the platform contract — between infrastructure primitives and higher-level developer abstractions.

## Engineering Knowledge
💡 **Engineering Knowledge — Internal Developer Platform**: The IDP is how platform teams scale without becoming bottlenecks. The goal is self-service: stream-aligned teams should be able to provision, deploy, and operate their services without filing a ticket. Design the platform contract first — what does the platform provide, and what API does it expose? Then build the Golden Path: the path of least resistance to production that includes CI/CD, observability, and security by default. Adoption is your metric. If teams bypass the platform, that is a platform design problem, not a discipline problem. → `engineering-knowledge-repository/internal-developer-platform.md`

## Related Entries
- [Internal Developer Portal](internal-developer-portal.md) — the self-service UI and service catalog that surfaces the platform's capabilities
- [Golden Path](golden-path.md) — the opinionated default path the IDP maintains for stream-aligned teams
- [Team Topologies](team-topologies.md) — platform teams are a defined Team Topologies team type; cognitive load reduction is the design goal
- [Twelve-Factor App](twelve-factor-app.md) — twelve-factor principles inform what the platform should manage vs. what the app should own
- [GitOps](gitops.md) — a common IDP deployment pattern where Git is the source of truth for infrastructure and application state

---
id: platform-as-a-product
tags: [methodology, team-practices, developer-experience]
surfaces-at: [application-design]
related: [team-topologies, internal-developer-portal, developer-experience, inner-source, four-key-metrics]
complexity: intermediate
---

# Platform as a Product

## What It Is
A philosophy for building and managing internal platforms — treating the platform not as an internal IT function but as a product with real users (the development teams), a product roadmap, customer discovery practices, and measurable value delivery. When a platform team treats its infrastructure, tooling, and self-service capabilities as a product, it shifts from reactive ticket-driven operations to proactive capability delivery aligned with developer needs. The concept is central to Team Topologies' Platform Team archetype and the DevOps Platform Engineering movement.

## When to Apply
- Any organization with a dedicated platform, infrastructure, or DevOps team
- When development teams are blocked by platform team queues or slow self-service capabilities
- When platform teams have no visibility into whether their investments are delivering value
- Scaling organizations building shared internal infrastructure that multiple product teams consume
- When transitioning from a centralized IT operations model to an engineering-led platform model

## Key Concepts
- **Users are Development Teams**: The platform's customers are the engineers who use it. Platform teams apply customer discovery practices: user interviews, usage analytics, feedback channels, and NPS surveys to understand what the platform does well and where it creates friction
- **Product Roadmap**: Platform capabilities are prioritized on a roadmap based on developer impact, not just technical debt or infrastructure hygiene. The roadmap is visible to consuming teams so they know what's coming and can plan around it
- **Self-Service by Default**: The platform's primary mode of delivery is self-service — developers provision databases, configure CI/CD pipelines, create services, and request secrets without filing tickets. The platform team's job is to make self-service reliable and simple, not to be the bottleneck
- **Golden Paths**: Opinionated, well-supported paths through the platform for common tasks (e.g., "how to create a new Python service", "how to deploy to EKS"). Golden paths encode best practices and reduce cognitive load. They are opt-in — teams can deviate, but the path is the fastest route
- **Platform-as-Product Metrics**: Platforms measure their success through developer-facing metrics: time to onboard a new service, CI/CD cycle time, DORA metrics (across all teams), developer satisfaction score, percentage of teams using self-service. Not just infrastructure availability
- **Thinnest Viable Platform**: The platform should provide the minimum capability set that enables teams to move fast safely. Don't over-engineer abstractions before demand is clear. Expand the platform based on real developer pain points, not anticipated needs
- **Internal Open Source / InnerSource**: Platform code is often developed using InnerSource practices — consuming teams contribute improvements via pull requests; the platform team reviews and merges. This distributes ownership and avoids the platform team becoming the only people who can change platform code
- **Platform Team as Enabling Team**: In Team Topologies, platform teams are "Enabling Teams" — they exist to reduce cognitive load on stream-aligned (product) teams, not to own delivery. When platform teams become delivery bottlenecks, the model has failed

## In Practice
Method platform engineering engagements frame the platform team's work as a product. At engagement start, the platform team identifies its "customers" (product engineering teams) and conducts a developer experience audit to find the highest-friction areas. Capability roadmaps are built around friction reduction. CI/CD templates, service scaffolding, and secrets management are delivered as golden paths. Quarterly developer NPS scores track platform value delivery.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Platform as a Product**: The failure mode of platform teams is building sophisticated infrastructure that development teams don't use — because it's too complex, not self-service, or misaligned with what developers actually need. Treating the platform as a product forces the discipline of customer discovery: talk to your users (developers), measure adoption, and ruthlessly prioritize the capabilities that unblock the most teams. The thinnest viable platform that development teams actually use beats the most sophisticated platform they route around. → `engineering-knowledge-repository/platform-as-a-product.md`

## Related Entries
- [Team Topologies](team-topologies.md) — Platform as a Product is the operating model for Team Topologies' Platform Team archetype
- [Internal Developer Portal](internal-developer-portal.md) — the IDP is the primary surface through which a platform-as-product exposes its capabilities
- [Developer Experience](developer-experience.md) — platform teams measure their success through developer experience outcomes
- [InnerSource](inner-source.md) — platform code is often developed with InnerSource practices to distribute ownership
- [Four Key Metrics](four-key-metrics.md) — DORA metrics measure the platform team's impact on engineering delivery performance

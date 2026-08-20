---
id: twelve-factor-app
tags: [reference, backend, cloud, deployment]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [evolutionary-architecture, serverless, microservices]
complexity: foundational
---

# The Twelve-Factor App

## What It Is
A methodology for building software-as-a-service applications that are portable, scalable, and maintainable. Codified by Heroku engineers based on patterns observed across thousands of deployments. The twelve factors address configuration, dependencies, process model, deployment, and operations in a way that enables cloud-native deployment without lock-in.

## When to Apply
- Any application being deployed to a cloud platform or container environment
- When portability across environments (dev, staging, prod) is required
- Microservices or distributed systems where operational consistency matters
- When building for scale — the twelve factors are prerequisites for horizontal scaling

## When Not to Apply
- Monolithic desktop applications or embedded systems
- Very simple scripts or tools not deployed as services
- Don't mechanically apply all twelve factors when only a subset is relevant to your context

## Key Concepts
- **I. Codebase**: One codebase tracked in version control, many deploys
- **II. Dependencies**: Explicitly declare and isolate dependencies (package.json, pom.xml, requirements.txt)
- **III. Config**: Store config in the environment — not in code. Anything that varies between deploys (URLs, credentials, feature flags) lives in environment variables
- **IV. Backing Services**: Treat backing services (databases, queues, caches) as attached resources — swappable via config change, not code change
- **V. Build/Release/Run**: Strictly separate build, release, and run stages
- **VI. Processes**: Execute as stateless processes — no sticky sessions, no local filesystem state
- **VII. Port Binding**: Export services via port binding — the app is self-contained
- **VIII. Concurrency**: Scale out via the process model, not via threads within a single process
- **IX. Disposability**: Fast startup and graceful shutdown — designed for ephemeral processes
- **X. Dev/Prod Parity**: Keep dev, staging, and production as similar as possible
- **XI. Logs**: Treat logs as event streams — write to stdout, let the environment aggregate
- **XII. Admin Processes**: Run admin/management tasks as one-off processes in the same environment

## In Practice
Factor III (Config in environment) and Factor VI (Stateless processes) are the most commonly violated and the most impactful to fix. Hard-coded config is the #1 source of "it works on my machine" problems. Stateful processes are the #1 barrier to horizontal scaling. In NFR Requirements, the twelve factors surface as deployment and operational requirements. In Infrastructure Design, they inform container and cloud configuration decisions.

## Engineering Knowledge
💡 **Engineering Knowledge — Twelve-Factor App**: Before deciding how to deploy, check your app against the twelve factors. Config in environment variables? Stateless processes? Fast startup and graceful shutdown? These aren't nice-to-haves for cloud deployment — they're prerequisites. Violations discovered in production are expensive. → `engineering-knowledge-repository/architectural-philosophy/twelve-factor-app.md`

## Related Entries
- [Evolutionary Architecture](evolutionary-architecture.md) — twelve-factor apps are inherently more evolvable
- [Serverless](../architectural-styles/serverless.md) — serverless platforms enforce many twelve-factor principles automatically
- [Microservices](../architectural-styles/microservices.md) — twelve-factor is foundational for microservices deployment

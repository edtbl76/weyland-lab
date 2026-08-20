---
id: immutable-infrastructure
tags: [pattern, deployment, cloud, infrastructure]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [infrastructure-as-code, gitops, blue-green-deployment, continuous-deployment]
complexity: intermediate
---

# Immutable Infrastructure

## What It Is
An approach where infrastructure components (servers, containers) are never modified in place after deployment. When a change is needed — configuration update, dependency upgrade, bug fix — a new image is built, tested, and deployed; the old one is replaced and discarded. The infrastructure is treated as disposable and replaceable, not as a long-lived asset to be patched and maintained. "Cattle, not pets."

## When to Apply
- Container-based deployments — immutability is inherent in Docker/Kubernetes: images are built, not patched
- Cloud VM deployments where server drift and configuration management complexity is a problem
- Systems requiring auditability — knowing exactly what is deployed (the exact image SHA)
- When server drift (accumulated manual changes) is causing reliability problems

## When Not to Apply
- Legacy systems with stateful servers holding data that can't be externalized — requires migration to external state first
- Environments where build and deploy times are too long for the required change frequency
- On-premises hardware where the replace-and-discard model isn't practical

## Key Concepts
- **Immutable Image**: A server image (AMI, Docker image) built once and deployed unchanged — no patching, no SSH-in-and-fix
- **Phoenix Server**: Servers are regularly replaced from a known-good base image rather than patched in place — named after the mythological bird rising from ashes
- **Snowflake Server Anti-Pattern**: Servers that have been patched, configured, and modified over time until no two are alike — the opposite of immutable
- **Cattle vs. Pets**: Pets are individual servers you care about and nurse back to health when sick. Cattle are instances you replace when they fail.
- **Externalized State**: Immutable infrastructure requires all persistent state (databases, files, config) to live outside the server — in managed databases, object storage, or secrets managers
- **Build Pipeline**: Immutable images are built via a CI pipeline that runs tests before the image is considered deployment-ready

## In Practice
Immutable infrastructure is the default in container-native (Kubernetes) deployments at Method — Docker images are inherently immutable. For VM-based environments, the Packer + Terraform stack builds and deploys AMIs without manual server configuration. The key shift is cultural: resist the urge to SSH in and fix; rebuild and redeploy instead.

## Engineering Knowledge
💡 **Engineering Knowledge — Immutable Infrastructure**: Never patch a running server. Build a new image, deploy it, retire the old one. Containers make this the default — every `docker build` produces an immutable image. For VMs, use Packer to build AMIs and Terraform to deploy them. No SSH-in-and-fix: if it's broken, rebuild. Externalizing all state is the prerequisite — no state lives on the server. → `engineering-knowledge-repository/deployment/immutable-infrastructure.md`

## Related Entries
- [Infrastructure as Code](infrastructure-as-code.md) — IaC makes rebuilding infrastructure cheap, enabling immutability
- [GitOps](gitops.md) — GitOps manages the desired state that immutable images are deployed to
- [Blue-Green Deployment](blue-green-deployment.md) — immutable infrastructure enables zero-downtime blue-green deploys

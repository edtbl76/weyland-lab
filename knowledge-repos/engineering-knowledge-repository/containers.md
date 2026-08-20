---
id: containers
tags: [tooling, infrastructure, deployment, backend]
surfaces-at: [infrastructure-design, code-generation]
related: [kubernetes, infrastructure-as-code, twelve-factor-app, security-hardening, ci-cd]
complexity: beginner
---

# Containers

## What It Is
A lightweight, portable packaging format that bundles an application with all its dependencies — runtime, libraries, configuration — into an isolated unit that runs consistently across any environment. Containers share the host OS kernel (unlike VMs) making them fast to start and resource-efficient. Docker is the dominant container runtime and image format. Containers are the foundational building block of modern cloud deployment — they enable the "build once, run anywhere" promise and are the unit of deployment in Kubernetes.

## When to Apply
- Packaging any application for deployment — containers are the default deployment artifact
- Ensuring consistency between development, staging, and production environments
- Microservices architectures where each service is independently deployable
- Any workload running on Kubernetes or a container orchestration platform

## Key Concepts
- **Dockerfile**: A declarative build script that defines a container image layer by layer. Each instruction (FROM, RUN, COPY) creates an image layer. Layers are cached — ordering instructions from least to most frequently changed maximizes cache hits and build speed
- **Image**: An immutable, versioned snapshot of the container filesystem. Built from a Dockerfile; stored in a registry (ECR, Docker Hub, GCR). Tagged by version or git SHA
- **Container**: A running instance of an image. Ephemeral by design — containers are created and destroyed freely. State must be stored externally (database, object storage) — never in the container filesystem
- **Base Image Selection**: Start from minimal base images — `python:3.11-slim`, `node:20-alpine` — rather than full OS images. Smaller images are faster to pull, have a smaller attack surface, and cost less in registry storage
- **Multi-Stage Builds**: Use multiple FROM stages in one Dockerfile — build stage compiles code with full toolchain; final stage copies only the artifact into a minimal runtime image. Dramatically reduces final image size
- **Layer Caching**: Place infrequently changing instructions (installing system packages) before frequently changing ones (copying application code). Cache misses invalidate all subsequent layers
- **Container Registry**: Storage and distribution for container images. ECR (AWS), GCR (GCP), ACR (Azure), Docker Hub. Integrate registry scanning for vulnerability detection on every image push
- **Secrets**: Never bake secrets into container images — they become part of the image layer history. Inject secrets at runtime via environment variables, mounted volumes, or secrets managers
- **Resource Limits**: Containers without CPU and memory limits can starve other containers on the same host. Always set limits in production (enforced by Kubernetes resource limits)
- **Immutable Infrastructure**: Containers embody immutable infrastructure — never modify a running container; build a new image and redeploy. This makes deployments reproducible and rollbacks straightforward

## In Practice
Method builds container images in CI using multi-stage Dockerfiles. Base images are pinned to specific digests for reproducibility. Images are scanned for vulnerabilities with Trivy before pushing to ECR. Secrets are injected via AWS Secrets Manager at runtime. All production containers run with explicit CPU and memory limits.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Containers**: Use multi-stage builds to minimize final image size — compile in one stage, copy the artifact to a minimal runtime image. Pin base images to specific digests for reproducibility; use slim/alpine variants to minimize attack surface. Never put secrets in images — inject at runtime. Order Dockerfile instructions from stable to frequently changing to maximize layer cache efficiency. Scan images for vulnerabilities in CI before pushing. Treat containers as immutable — never exec into a running container to make changes; build and redeploy instead. → `engineering-knowledge-repository/containers.md`

## Related Entries
- [Kubernetes](kubernetes.md) — Kubernetes orchestrates containers at scale
- [Infrastructure as Code](infrastructure-as-code.md) — Dockerfiles and container configs are infrastructure as code artifacts
- [Twelve-Factor App](twelve-factor-app.md) — twelve-factor principles align closely with container best practices
- [Security Hardening](security-hardening.md) — container image hardening is a key security practice
- [CI/CD](ci-cd.md) — container images are built, scanned, and pushed in CI/CD pipelines

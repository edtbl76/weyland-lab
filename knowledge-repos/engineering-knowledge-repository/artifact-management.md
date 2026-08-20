---
id: artifact-management
tags: [pattern, deployment, infrastructure, backend]
surfaces-at: [infrastructure-design, application-design]
related: [ci-cd, containers, kubernetes, immutable-infrastructure, semantic-versioning]
complexity: foundational
---

# Artifact Management

## What It Is
The practices and tooling for producing, storing, versioning, and distributing build outputs — compiled binaries, container images, libraries, and deployment packages. An artifact repository is the authoritative store for what gets deployed. Every build produces an immutable, versioned artifact; deployments pull from the artifact store rather than rebuilding at deploy time. This ensures that what was tested in staging is exactly what runs in production, and that any version can be redeployed or rolled back without rebuilding.

## When to Apply
- Any CI/CD pipeline producing deployable outputs
- Container-based deployments (every image needs a registry)
- Library or package authoring (internal npm/PyPI/Maven packages)
- Any system where rollback or auditability of deployed versions matters

## Key Concepts
- **Artifact Types**:
  - *Container images*: Stored in container registries (ECR, Docker Hub, GCR, ACR). Tagged by version and commit SHA
  - *Language packages*: npm packages, Python wheels, Maven JARs stored in private registries (Artifactory, Nexus, GitHub Packages)
  - *Build binaries*: Go binaries, Lambda ZIPs, deployment packages stored in S3 or artifact stores
- **Container Registries**:
  - *AWS ECR*: Fully managed; integrates with ECS, EKS, and IAM. Lifecycle policies automate old image cleanup
  - *Docker Hub*: Public registry; rate-limited for unauthenticated pulls. Use for open source; use private registry for production
  - *GitHub Container Registry (GHCR)*: Integrated with GitHub Actions; good for open source and GitHub-native workflows
  - *Harbor*: Self-hosted, open-source registry with vulnerability scanning and policy enforcement
- **Tagging Strategy**:
  - Tag images with both a semantic version (or `latest`) AND the Git commit SHA
  - `latest` is mutable — never deploy based on `latest` in production
  - Commit SHA tags are immutable — what you deployed is auditable
  - Example: `my-service:1.4.2` and `my-service:abc1234` pointing to the same image digest
- **Immutability**: Once published, an artifact should not change. Overwriting a tag breaks reproducibility and auditability. Use digest-pinned references (`image@sha256:...`) for the most secure deployments
- **Image Scanning**: Scan container images for known CVEs before deployment. Trivy, Snyk, and ECR enhanced scanning integrate into CI pipelines. Block deployments with critical vulnerabilities
- **Lifecycle Policies**: Registries accumulate images rapidly — define retention policies. ECR lifecycle policies delete untagged images older than N days, keeping tagged versions indefinitely
- **Promotion**: Artifacts are promoted through environments, not rebuilt. Build once → push to registry → deploy same artifact to dev → staging → prod. Rebuilding per environment risks environment-specific differences
- **Private Registries for Dependencies**: Pull base images and dependencies from a private registry or proxy (Artifactory, Nexus) to avoid rate limits, ensure availability, and control approved base images

## In Practice
Method uses AWS ECR for all container image storage. Images are tagged with Git commit SHA and semantic version. ECR lifecycle policies retain the last 20 tagged images and delete untagged images after 7 days. Trivy scans images in CI before push; critical CVEs block the build. Deployments reference commit SHA tags, never `latest`. Internal Python packages are published to a private CodeArtifact registry.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Artifact Management**: Build once, deploy the same artifact across environments — never rebuild per environment. Tag container images with Git commit SHAs, not just `latest` — `latest` is mutable and breaks auditability. Scan images for CVEs in CI before pushing to the registry. Define lifecycle policies to prevent registry storage from growing unbounded. When pulling dependencies in CI, cache or proxy through a private registry to avoid rate limits and supply chain risk. → `engineering-knowledge-repository/artifact-management.md`

## Related Entries
- [CI/CD](ci-cd.md) — CI pipelines build and push artifacts; CD pipelines deploy them from the registry
- [Containers](containers.md) — container images are the primary artifact type for modern deployments
- [Kubernetes](kubernetes.md) — Kubernetes pulls container images from registries at deployment time
- [Immutable Infrastructure](immutable-infrastructure.md) — immutable infrastructure relies on immutable, versioned artifacts as the unit of deployment
- [Semantic Versioning](semantic-versioning.md) — artifact version tags follow semantic versioning conventions

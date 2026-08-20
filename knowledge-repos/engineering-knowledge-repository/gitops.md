---
id: gitops
tags: [methodology, deployment, infrastructure]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [infrastructure-as-code, continuous-delivery, continuous-deployment, immutable-infrastructure]
complexity: intermediate
---

# GitOps

## What It Is
An operational framework where Git is the single source of truth for both application code and infrastructure configuration. The desired state of the system is declared in Git; an automated operator continuously reconciles the actual system state with the desired state in Git. Deployments happen by opening a pull request — not by running scripts. Promoted by Weaveworks; operationalized by tools like Argo CD and Flux.

## When to Apply
- Kubernetes-based environments where declarative configuration is already the norm
- Teams that want a full audit trail of all infrastructure and deployment changes in Git
- When operational changes are made ad-hoc and need to be brought under version control
- Multi-environment deployments (dev → staging → prod) managed through Git branch or directory promotion

## When Not to Apply
- Non-Kubernetes environments where the GitOps operator model doesn't apply cleanly
- Very small teams where the tooling overhead (Argo CD, Flux) isn't justified
- Systems with secrets that cannot be safely stored in Git (address with sealed secrets or external secrets operator)

## Key Concepts
- **Declarative Configuration**: Desired state is expressed as code (YAML manifests, Helm charts, Kustomize overlays) — not imperative scripts
- **Git as Single Source of Truth**: All changes to infrastructure and deployment must go through Git — no `kubectl apply` in production directly
- **Reconciliation Loop**: The GitOps operator (Argo CD, Flux) continuously compares desired state (Git) with actual state (cluster) and corrects drift
- **Pull-Based Deployment**: The cluster pulls configuration from Git — not pushed from CI. Safer: the cluster never needs external credentials; the CI pipeline never needs cluster access.
- **Drift Detection**: GitOps operators detect and can automatically or manually correct configuration drift
- **Audit Trail**: Every change to the deployed state is a Git commit — full history, attribution, and rollback via `git revert`

## In Practice
GitOps is Method's recommended deployment model for Kubernetes-based production systems. Argo CD is the standard tool — it provides a UI, diff views, and automated sync. The promotion pattern (manifests in separate repo or directory per environment) controls the path from dev to prod. Secrets management is the main complexity — use Sealed Secrets or External Secrets Operator to avoid plaintext credentials in Git.

## Engineering Knowledge
💡 **Engineering Knowledge — GitOps**: Deploy by merging a pull request. Git is the source of truth; the cluster reconciles itself to match. Every production change has a Git commit — full audit trail, instant rollback via `git revert`. Argo CD is the standard: it shows what's deployed, what differs from Git, and syncs automatically. Never `kubectl apply` to prod directly. Solve secrets with Sealed Secrets or External Secrets Operator — plaintext credentials don't belong in Git. → `engineering-knowledge-repository/deployment/gitops.md`

## Related Entries
- [Infrastructure as Code](infrastructure-as-code.md) — IaC declares infrastructure; GitOps uses Git to manage and deploy it
- [Continuous Delivery](continuous-delivery.md) — GitOps is the Kubernetes-native implementation of CD
- [Immutable Infrastructure](immutable-infrastructure.md) — GitOps and immutable infrastructure are natural companions

---
id: helm
tags: [tooling, deployment, infrastructure, kubernetes]
surfaces-at: [infrastructure-design]
related: [kubernetes, gitops, infrastructure-as-code, container-orchestration, ci-cd]
complexity: intermediate
---

# Helm

## What It Is
The package manager for Kubernetes. Helm bundles Kubernetes YAML manifests into reusable, parameterizable packages called charts. A chart defines all the resources needed to run an application (Deployments, Services, ConfigMaps, Ingress, RBAC) and exposes configuration knobs via a `values.yaml` file. Helm tracks deployed releases, enabling upgrades and rollbacks. Where raw Kubernetes YAML is static and repetitive, Helm provides templating, versioning, and lifecycle management for complex multi-resource deployments.

## When to Apply
- Deploying applications with multiple Kubernetes resources (Deployment + Service + ConfigMap + Ingress is already worth templating)
- Reusing deployment patterns across multiple services or environments
- Managing third-party software on Kubernetes (databases, monitoring, ingress controllers)
- Any team that needs to upgrade or roll back Kubernetes deployments as a unit

## Key Concepts
- **Chart Structure**:
  ```
  my-chart/
    Chart.yaml          # metadata: name, version, appVersion
    values.yaml         # default configuration values
    templates/          # Kubernetes YAML with Go template syntax
      deployment.yaml
      service.yaml
      ingress.yaml
    charts/             # sub-charts (dependencies)
  ```
- **Templates**: Kubernetes YAML with `{{ .Values.replicaCount }}` style substitutions. Helm renders templates by merging the chart's default values with user-supplied overrides at deploy time
- **Values**: Hierarchical configuration. Override defaults via:
  - `--values custom-values.yaml` — file-based overrides (per environment)
  - `--set key=value` — inline overrides (for CI/CD one-offs)
- **Release**: A named instance of a chart deployed to a namespace. Multiple releases of the same chart can coexist (e.g., `my-app-staging` and `my-app-production`)
- **Upgrade and Rollback**: `helm upgrade` applies changes; `helm rollback` reverts to a previous release revision. Helm stores release history in Kubernetes Secrets
- **Chart Repository**: Hosted collections of charts. Public repos: Artifact Hub, Bitnami. Private: OCI-compatible registries (ECR, GHCR), Chartmuseum
- **Dependencies**: Charts can declare sub-chart dependencies (e.g., a Postgres chart). `helm dependency update` fetches them into `charts/`
- **Helm vs. Raw YAML**: Helm adds templating and lifecycle management but increases complexity. For simple single-service deployments, Kustomize (pure YAML overlays) may be simpler. Helm shines for complex, reusable charts deployed across environments
- **Helm in GitOps**: FluxCD and ArgoCD both support Helm releases. A `HelmRelease` CR in Git describes the chart, version, and values — the GitOps controller reconciles the cluster state to match
- **Security Consideration**: Helm chart values may contain secrets. Use Helm Secrets plugin or external secrets management rather than committing secret values to values files in Git

## In Practice
Method uses Helm for Kubernetes deployments across services. Application charts follow a standard internal chart template. Per-environment values files (`values-staging.yaml`, `values-prod.yaml`) configure resource sizes, replica counts, and endpoints. ArgoCD manages Helm releases via GitOps. Third-party dependencies (nginx-ingress, cert-manager, kube-prometheus-stack) are deployed from public Helm charts with pinned versions.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Helm**: Helm solves the parameterization and lifecycle management problems of raw Kubernetes YAML — use it when you have multiple resources that need to be deployed, upgraded, and rolled back as a unit. Pin chart versions in production; don't use `latest`. Use per-environment values files rather than `--set` flags in CI to keep environment config in Git. For GitOps workflows, ArgoCD and FluxCD both support `HelmRelease` CRDs that declaratively manage Helm deployments from Git. Don't put secrets in values files — use Helm Secrets plugin or External Secrets Operator. → `engineering-knowledge-repository/helm.md`

## Related Entries
- [Kubernetes](kubernetes.md) — Helm is the standard package manager for Kubernetes deployments
- [GitOps](gitops.md) — ArgoCD and FluxCD manage Helm releases declaratively via Git
- [Infrastructure as Code](infrastructure-as-code.md) — Helm charts are the IaC mechanism for Kubernetes application deployments
- [Container Orchestration](container-orchestration.md) — Helm operates within the container orchestration layer to manage application lifecycle
- [CI/CD](ci-cd.md) — CI/CD pipelines use `helm upgrade` to deploy new versions

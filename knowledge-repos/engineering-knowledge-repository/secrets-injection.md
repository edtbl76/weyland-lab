---
id: secrets-injection
tags: [pattern, security, cloud, infrastructure]
surfaces-at: [infrastructure-design, nfr-design]
related: [secrets-management, container-orchestration, immutable-infrastructure, zero-trust-security]
complexity: intermediate
---

# Secrets Injection

## What It Is
The pattern of delivering secrets (API keys, database passwords, certificates) to running workloads at runtime rather than baking them into container images, code, or configuration files. Secrets are fetched from a secure store (AWS Secrets Manager, HashiCorp Vault, Kubernetes Secrets) and injected into the application as environment variables or mounted files — never committed to source control or embedded in artifacts.

## When to Apply
- Any containerized or cloud-native workload that requires credentials, API keys, or certificates
- Kubernetes deployments where secrets need to be managed separately from application configuration
- Multi-environment setups where credentials differ across dev, staging, and production
- Compliance-constrained systems requiring secrets audit trails and rotation support

## When Not to Apply
- Local development with non-sensitive dummy credentials in `.env` files (acceptable for dev-only)
- Static websites with no server-side secrets

## Key Concepts
- **Environment Variable Injection**: The simplest form — secrets are set as environment variables at container startup. Risk: env vars can appear in process listings and crash dumps
- **Volume-Mounted Secrets**: Secrets are written to an in-memory tmpfs volume and mounted into the container as files. More secure than env vars — not visible in process env
- **Kubernetes Secrets**: Built-in Kubernetes resource for storing base64-encoded secrets. Base64 is not encryption — enable envelope encryption with a KMS key for production
- **External Secrets Operator**: Kubernetes operator that syncs secrets from AWS Secrets Manager, Vault, or GCP Secret Manager into Kubernetes Secrets automatically
- **CSI Secrets Store Driver**: Mounts secrets from external stores directly as volumes into Pods — the store is authoritative; Kubernetes Secrets are not required
- **Init Container Pattern**: A privileged init container fetches secrets at Pod startup and writes them to a shared volume — main container reads from volume without direct store access
- **Secret Rotation**: Managed secret stores support automatic rotation. Applications must handle credential refresh — connection pool reconnect on auth failure

## In Practice
For Kubernetes workloads in Method engagements, the preferred pattern is External Secrets Operator syncing from AWS Secrets Manager into Kubernetes Secrets with KMS envelope encryption enabled. This keeps AWS Secrets Manager as the authoritative source while making secrets available natively to Kubernetes workloads. Never store production secrets in `values.yaml` or Helm chart defaults — use External Secrets or Sealed Secrets.

## Engineering Knowledge
💡 **Engineering Knowledge — Secrets Injection**: Never bake secrets into container images or commit them to source control. Inject at runtime from AWS Secrets Manager or Vault. In Kubernetes, use External Secrets Operator to sync secrets into Kubernetes Secrets with KMS encryption — AWS Secrets Manager stays authoritative. Enable secret rotation and make sure your apps handle credential refresh gracefully (reconnect on auth failure). Volume mounts are more secure than environment variables for sensitive secrets. → `engineering-knowledge-repository/cloud-patterns/secrets-injection.md`

## Related Entries
- [Secrets Management](../security/secrets-management.md) — the broader strategy for secret lifecycle and storage
- [Container Orchestration](container-orchestration.md) — Kubernetes Secrets and Pod secret mounting
- [Immutable Infrastructure](../deployment/immutable-infrastructure.md) — immutable images must not contain secrets
- [Zero Trust Security](../security/zero-trust-security.md) — secrets injection is part of a zero-trust posture

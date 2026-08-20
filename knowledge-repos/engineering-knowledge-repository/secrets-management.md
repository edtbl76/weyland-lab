---
id: secrets-management
tags: [pattern, security, infrastructure]
surfaces-at: [nfr-requirements, infrastructure-design, code-generation]
related: [zero-trust-security, principle-of-least-privilege, twelve-factor-app, infrastructure-as-code]
complexity: intermediate
---

# Secrets Management

## What It Is
The practice of securely storing, accessing, rotating, and auditing credentials, API keys, certificates, and other sensitive configuration values — keeping them out of source code, build artifacts, and environment variables baked into images. Secrets management platforms (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager) provide centralized, auditable, and rotatable credential storage with fine-grained access control.

## When to Apply
- All production systems — any system with credentials needs secrets management
- Before the first production deployment — retrofitting secrets management is painful
- When secrets are currently stored in environment variables baked into container images, config files checked into Git, or passed as plaintext in CI/CD pipelines

## When Not to Apply
- Local development can use `.env` files with appropriate `.gitignore` — don't over-engineer local dev secrets management
- Very simple internal tools where the operational overhead of a secrets manager isn't warranted — use environment variables via the platform (Kubernetes Secrets, Heroku config vars) at minimum

## Key Concepts
- **Never in Code**: Secrets must never be committed to source control — use pre-commit hooks (detect-secrets, gitleaks) to prevent accidental commits
- **Dynamic Secrets**: Short-lived credentials generated on-demand for each service (Vault dynamic secrets for databases) — rotation is automatic, no long-lived shared credentials
- **Static Secrets with Rotation**: For credentials that can't be dynamic — store in Secrets Manager, rotate on a schedule, audit access
- **Least Privilege Access**: Services access only the secrets they need — Vault policies or IAM conditions restrict which service can read which secret
- **Injection at Runtime**: Secrets are injected at service startup via environment variables or mounted files — not baked into images or config files
- **Audit Trail**: Every secret read is logged — who accessed what, when
- **Secret Sprawl**: The anti-pattern of secrets scattered across multiple storage systems with no central governance

## In Practice
AWS Secrets Manager is Method's standard for AWS-based engagements — native IAM integration, automatic rotation for RDS credentials, SDK support in all languages. HashiCorp Vault for multi-cloud or on-premises environments. Establish secret management in Iteration 0 — retrofit is significantly more work. Use `detect-secrets` pre-commit hooks on all repos.

## Engineering Knowledge
💡 **Engineering Knowledge — Secrets Management**: Never put secrets in code, never bake them into images, never store them in plaintext config files. Use AWS Secrets Manager or Vault — inject credentials at runtime, rotate them automatically, audit who accessed what. Add `detect-secrets` to your pre-commit hooks to catch accidental commits. The most dangerous credentials are the ones that were leaked in a commit 18 months ago and nobody noticed. → `engineering-knowledge-repository/security/secrets-management.md`

## Related Entries
- [Zero Trust Security](zero-trust-security.md) — secrets management is a core Zero Trust mechanism
- [Twelve-Factor App](../architectural-philosophy/twelve-factor-app.md) — Factor III: config in environment, not code
- [Infrastructure as Code](../deployment/infrastructure-as-code.md) — secrets referenced from Secrets Manager in IaC, never stored in plaintext

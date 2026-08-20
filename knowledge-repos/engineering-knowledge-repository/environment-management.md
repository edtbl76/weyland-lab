---
id: environment-management
tags: [pattern, deployment, infrastructure, backend]
surfaces-at: [infrastructure-design, application-design]
related: [twelve-factor-app, infrastructure-as-code, gitops, ci-cd, secrets-management, feature-flags]
complexity: intermediate
---

# Environment Management

## What It Is
The practices for creating, configuring, and maintaining the multiple deployment environments (development, staging, production, and optionally preview/ephemeral) through which software travels before reaching users. Good environment management ensures that environments are as similar as possible — reducing "works on my machine" and staging-to-production discrepancies — while allowing appropriate isolation between them. Configuration, secrets, and infrastructure topology vary per environment; the application code and artifacts do not.

## When to Apply
- Any team deploying software to a shared service (i.e., almost everything)
- Services where staging failures and production failures need to be isolated
- Teams doing continuous delivery with multiple environments in the pipeline
- Systems requiring environment-specific configuration (endpoints, feature flags, resource sizing)

## Key Concepts
- **Environment Tiers**:
  - *Development*: Individual developer environments (local or cloud dev environments). Fast iteration; may use mocked dependencies
  - *Staging*: Production-like environment for integration testing, QA, and pre-release validation. Should mirror production topology
  - *Production*: Live user traffic. Change-controlled; monitored; high availability
  - *Preview / Ephemeral*: Short-lived environments created per pull request or branch for isolated testing. Torn down after merge
- **Environment Parity**: The twelve-factor app principle — dev, staging, and prod should be as similar as possible. Gaps cause deployment surprises:
  - Same OS, runtime version, and dependency versions
  - Same infrastructure services (not SQLite in dev and PostgreSQL in prod)
  - Same configuration structure (only values differ, not keys)
- **Configuration Per Environment**: Values that differ by environment (database URLs, feature flags, resource limits) are injected via environment variables or a configuration service — never hardcoded. Same artifact, different config
- **Environment Isolation**: Environments must not share state. Separate databases, separate message queues, separate secrets. A staging bug should never affect production data
- **Infrastructure as Code for Environments**: Environments are defined in code (Terraform, Pulumi, CloudFormation) — not manually configured. Consistent across environments; reproducible; auditable
- **Ephemeral Environments**: Create a full-stack environment per PR using IaC and tear it down after merge. Tools: Terraform workspaces, Pulumi stacks, Review Apps (Heroku), GitHub Environments. Enables integration testing in isolation without conflicts
- **Environment Promotion**: Code and artifacts are promoted through environments in sequence — not deployed directly to production. CI deploys to dev automatically; staging requires a passing pipeline; production requires approval
- **Environment-Specific Sizing**: Production resources are sized for load; staging and dev are downsized to reduce cost. Same topology, smaller instances. Avoid using serverless in staging if production uses dedicated containers — topology parity matters more than instance size
- **Configuration Management Tools**: AWS SSM Parameter Store, HashiCorp Vault, AWS AppConfig, or environment variables injected by the orchestrator. Avoid environment-specific config files committed to source control

## In Practice
Method maintains dev, staging, and production environments defined in Terraform. Ephemeral preview environments are created per pull request via GitHub Actions and Terraform workspaces. Secrets differ per environment via AWS Secrets Manager; the application code and container images are identical. Staging mirrors production topology at reduced instance sizes. Feature flags via LaunchDarkly allow production testing without separate environment promotion.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Environment Management**: Environment divergence is the root cause of most "works in staging, broken in production" incidents — use the same runtime, same infrastructure services, and same configuration keys across all environments. Define environments in code (IaC), not by manual console clicks. Isolate state completely — separate databases and queues per environment, never shared. Use ephemeral environments for PR-level integration testing to catch issues before staging. Downsize dev/staging resources but preserve the topology — a topology mismatch (e.g., PostgreSQL in prod, SQLite in staging) will hide real bugs. → `engineering-knowledge-repository/environment-management.md`

## Related Entries
- [Twelve-Factor App](twelve-factor-app.md) — factors III (config) and X (dev/prod parity) define environment management principles
- [Infrastructure as Code](infrastructure-as-code.md) — environments are reproduced via IaC for consistency and auditability
- [GitOps](gitops.md) — GitOps manages environment state via Git, making promotion explicit and auditable
- [CI/CD](ci-cd.md) — CI/CD pipelines orchestrate environment promotion from dev through staging to production
- [Secrets Management](secrets-management.md) — each environment has isolated secrets — no shared credentials across environments
- [Feature Flags](feature-flags.md) — feature flags decouple deployment from release, reducing the need for environment-level feature toggling

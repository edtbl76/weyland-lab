---
id: deployment-gates
tags: [pattern, deployment, reliability, testing]
surfaces-at: [infrastructure-design, application-design]
related: [ci-cd, canary-deployment, feature-flags, health-checks, observability-cost-management]
complexity: intermediate
---

# Deployment Gates

## What It Is
Automated checkpoints in a deployment pipeline that block promotion to the next environment or phase unless defined quality criteria are met. A deployment gate is a pass/fail evaluation — automated tests, security scans, performance thresholds, or approval workflows — that prevents a bad deployment from advancing before humans ever see the impact. Gates shift quality enforcement left: catch failures in CI before they reach staging, and catch regressions in staging before they reach production.

## When to Apply
- Any CI/CD pipeline with multiple environment stages (dev → staging → prod)
- Production deployments where regressions have significant business impact
- Canary or progressive rollout pipelines requiring automated health monitoring
- Systems with compliance requirements that need mandatory approval workflows

## Key Concepts
- **Pre-deployment Gates**: Evaluate before deployment begins
  - Unit and integration test pass rates
  - Code coverage thresholds (e.g., fail if coverage drops below 80%)
  - Static analysis and linting pass
  - Security scan results (Snyk, OWASP dependency check, SAST)
  - Container image vulnerability scan (Trivy, ECR scanning)
  - License compliance checks
- **Post-deployment Gates (Automated Canary Analysis)**: Evaluate after deploying to a subset of traffic
  - Error rate comparison: canary vs. baseline
  - Latency percentile comparison (p99 latency of canary vs. stable)
  - Business metric regression (conversion rate, throughput)
  - Tools: Flagger, Argo Rollouts, Spinnaker automated canary analysis (Kayenta)
- **Approval Gates**: Manual sign-off required before promotion
  - Product owner approval for staging → production
  - Change advisory board (CAB) approval for regulated environments
  - GitHub Environments with required reviewers
  - ServiceNow change requests integrated into pipelines
- **Infrastructure Gate Examples**:
  - Terraform plan review — require human approval of `terraform plan` output before `apply`
  - Database migration dry-run — validate migration SQL syntax before execution
  - Cost estimation gate — block if infrastructure cost change exceeds a threshold
- **Rollback Gates**: Trigger automatic rollback if post-deployment metrics degrade
  - Flagger and Argo Rollouts monitor metrics during progressive rollouts; automatically roll back if SLOs are breached
- **Gate Failure Behavior**: A failing gate must block the deployment, create visible evidence (failed pipeline stage, Slack alert, GitHub status check), and not require manual cleanup
- **Balancing Rigor and Velocity**: Too many gates slow delivery without proportional risk reduction. Focus gates on the highest-signal checks: security scans, test failures, error rate regression. Don't gate on low-signal checks (style warnings, non-critical coverage nudges)

## In Practice
Method CI/CD pipelines enforce pre-deployment gates: unit tests, integration tests, Trivy image scan, and Snyk dependency audit. Staging deployments require all gates to pass. Production deployments additionally require product owner approval via GitHub Environments. Canary deployments use Argo Rollouts with automated error rate and latency gates; rollback triggers if error rate exceeds 1% or p99 latency degrades by more than 20%.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Deployment Gates**: Gates are only valuable if they block on real signals — high false-positive rates train teams to ignore or bypass them. Prioritize security scans and error rate regression; de-prioritize coverage percentage warnings. Post-deployment canary gates (automated analysis of error rate and latency vs. baseline) catch regressions that pre-deployment tests miss. Approval gates are a last resort — automation catches most issues faster and without the bottleneck. Ensure failed gates produce clear, actionable output; a gate that fails with no guidance is just friction. → `engineering-knowledge-repository/deployment-gates.md`

## Related Entries
- [CI/CD](ci-cd.md) — deployment gates are checkpoints within CI/CD pipelines
- [Canary Deployment](canary-deployment.md) — post-deployment gates drive automated canary analysis and rollback decisions
- [Feature Flags](feature-flags.md) — feature flags reduce the need for strict deployment gates by enabling runtime rollback without redeployment
- [Health Checks](health-checks.md) — post-deployment health check results feed into gate evaluation

---
id: terraform
tags: [tooling, infrastructure, deployment]
surfaces-at: [infrastructure-design]
related: [infrastructure-as-code, gitops, kubernetes, ci-cd, secrets-management, vpc-and-networking]
complexity: intermediate
---

# Terraform

## What It Is
The dominant open-source infrastructure-as-code tool by HashiCorp. Terraform uses a declarative configuration language (HCL) to define cloud resources — compute, networking, databases, IAM, and services across AWS, GCP, Azure, and hundreds of providers. Engineers describe the desired end state; Terraform generates an execution plan (`terraform plan`) showing what will be created, changed, or destroyed, then applies it. State is tracked in a state file, enabling Terraform to detect drift between declared and actual infrastructure. Terraform is the de facto standard for cloud infrastructure provisioning at scale.

## When to Apply
- Any cloud infrastructure that needs to be reproducible, version-controlled, and team-maintained
- Multi-cloud or multi-provider infrastructure provisioning
- When infrastructure changes need review (plan output in pull requests) before apply
- Wherever manual console-click infrastructure exists that should be codified

## Key Concepts
- **HCL (HashiCorp Configuration Language)**: Terraform's declarative DSL. Resources, variables, outputs, and modules are defined in `.tf` files
  ```hcl
  resource "aws_s3_bucket" "artifacts" {
    bucket = "my-app-artifacts-${var.environment}"
    tags   = { Environment = var.environment }
  }
  ```
- **State File**: Terraform tracks infrastructure state in a `.tfstate` file mapping declared resources to real cloud resources. State must be stored remotely for team use (S3 + DynamoDB locking is the AWS standard). Never commit state to version control (may contain secrets)
- **Remote State Backend**: Store state in S3 with DynamoDB locking to prevent concurrent applies. Multiple environments use separate state files (separate S3 keys or separate workspaces)
- **Plan/Apply Workflow**:
  1. `terraform init` — download providers and modules
  2. `terraform plan` — generate execution plan (what will change)
  3. Human reviews plan
  4. `terraform apply` — execute the plan
  - Always review plan output before applying in production. Use `terraform plan -out=plan.tfplan` and `terraform apply plan.tfplan` to apply exactly the reviewed plan
- **Modules**: Reusable, parameterizable infrastructure building blocks. Extract common patterns (VPC, ECS service, RDS cluster) into modules for consistency across environments and projects. Public registry: `registry.terraform.io`
- **Workspaces**: Terraform workspaces maintain separate state files from the same configuration. Use for ephemeral environments (PR preview environments). Use separate directories/repos for long-lived environment configurations (dev/staging/prod) — not workspaces, which are harder to reason about
- **Variables and Outputs**: Input variables (`var.environment`) parameterize configurations. Outputs expose resource attributes (RDS endpoint, S3 bucket name) for use by other modules or downstream tooling
- **Provider Pinning**: Pin provider versions in `required_providers` block. Unpinned providers auto-update and can break configurations with breaking changes. Update providers intentionally, not silently
- **Terraform Cloud / Atlantis**: Atlantis (open source) or Terraform Cloud manage plan/apply in CI/CD. Post `terraform plan` output to pull requests for review; auto-apply on merge. Removes the need for engineers to run Terraform locally with production credentials
- **Drift Detection**: Terraform can detect when real infrastructure has diverged from declared state (`terraform plan` shows the drift). Schedule periodic plan runs in CI to detect manual changes or external modifications
- **OpenTofu**: The open-source fork of Terraform maintained by the Linux Foundation, created after HashiCorp changed Terraform's license to BSL. API-compatible with Terraform; growing adoption

## In Practice
Method uses Terraform for all AWS infrastructure. Remote state lives in S3 with DynamoDB locking per environment. Atlantis manages plan/apply in CI — `terraform plan` runs on PR open, `terraform apply` runs on merge to main. Modules for VPC, ECS service, RDS cluster, and ALB are maintained in an internal module registry. Provider versions are pinned; updates are done deliberately with plan review. Secrets are not stored in Terraform state — they live in AWS Secrets Manager.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Terraform**: Always run `terraform plan` and review the diff before `terraform apply` in production — a `destroy` in the plan output has ended careers. Store state in S3 + DynamoDB locking; never on local disk for team infrastructure. Use modules to avoid copying the same resource blocks across environments — a VPC module updated in one place propagates to all environments. Pin provider versions — silent provider upgrades break configurations. Don't store secrets in Terraform variables or state; reference them from Secrets Manager at runtime. Consider Atlantis or Terraform Cloud to enforce plan-review-before-apply for all team members. → `engineering-knowledge-repository/terraform.md`

## Related Entries
- [Infrastructure as Code](infrastructure-as-code.md) — Terraform is the primary implementation tool for the infrastructure-as-code methodology
- [GitOps](gitops.md) — Terraform in CI/CD with Atlantis implements GitOps for infrastructure changes
- [Kubernetes](kubernetes.md) — Terraform provisions the Kubernetes cluster; Helm and kubectl manage workloads within it
- [CI/CD](ci-cd.md) — Terraform plan/apply runs as a CI/CD stage with mandatory review before production apply
- [Secrets Management](secrets-management.md) — secrets should live in Secrets Manager, not Terraform variables or state
- [VPC and Networking](vpc-and-networking.md) — VPC architecture is defined and managed via Terraform

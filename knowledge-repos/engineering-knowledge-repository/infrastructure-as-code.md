---
id: infrastructure-as-code
tags: [methodology, infrastructure, deployment]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [gitops, immutable-infrastructure, cloud-native-design, continuous-delivery]
complexity: intermediate
---

# Infrastructure as Code (IaC)

## What It Is
The practice of managing and provisioning infrastructure through machine-readable configuration files rather than manual processes or interactive configuration tools. Infrastructure is described in code, version-controlled in Git, reviewed like application code, and applied by automation. Common tools: Terraform (declarative, multi-cloud), AWS CloudFormation (declarative, AWS-native), Pulumi (imperative, uses real programming languages), AWS CDK, Ansible.

## When to Apply
- Any production cloud environment — IaC is a baseline engineering practice, not an advanced technique
- When infrastructure changes must be reproducible, reviewable, and auditable
- When multiple environments (dev, staging, prod) must be kept consistent
- Disaster recovery: the ability to recreate infrastructure from code is the foundation of any DR plan

## When Not to Apply
- Truly ephemeral scratch environments — manual setup is fine for a 2-hour experiment
- Configurations managed by platform teams that provide self-service abstractions — consuming the platform doesn't require writing raw IaC

## Key Concepts
- **Declarative vs. Imperative**: Declarative (Terraform, CloudFormation) defines desired end state — the tool figures out how to get there. Imperative (Ansible, scripts) defines the steps to execute.
- **State**: Terraform tracks current infrastructure state in a state file — the diff between state and config determines what changes to apply. State must be stored remotely (S3 + DynamoDB) for team use.
- **Plan / Apply**: `terraform plan` previews changes without applying them — review before apply is the safety mechanism
- **Drift**: Manual changes to infrastructure outside of IaC create drift — IaC may overwrite them on next apply
- **Modules**: Reusable IaC components encapsulating common infrastructure patterns (VPC, ECS service, RDS cluster)
- **Environment Parity**: Same IaC modules with different variable sets produce dev, staging, and prod environments — reduces "works in staging, fails in prod" surprises

## In Practice
Terraform is Method's standard IaC tool for multi-cloud and AWS work. Remote state in S3 with DynamoDB locking is the standard setup. Module design is the key skill — well-designed modules encode organizational best practices and can be reused across engagements. IaC is established in Iteration 0 as part of infrastructure setup.

## Engineering Knowledge
💡 **Engineering Knowledge — Infrastructure as Code**: Provision every cloud resource through code, not the console. IaC gives you reproducible environments, Git history for every infrastructure change, and the ability to recreate everything from scratch for DR. Terraform is the standard: declarative config, `plan` before `apply`, remote state in S3. Modules encode infrastructure patterns — write once, reuse across environments and engagements. Manual console changes create drift; IaC owns the truth. → `engineering-knowledge-repository/deployment/infrastructure-as-code.md`

## Related Entries
- [GitOps](gitops.md) — GitOps uses IaC managed in Git with automated reconciliation
- [Immutable Infrastructure](immutable-infrastructure.md) — IaC enables immutable infrastructure by making recreation cheap
- [Cloud Native Design](../cloud-patterns/cloud-native-design.md) — IaC is a prerequisite for cloud-native operations

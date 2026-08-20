---
id: cloud-iam
tags: [cloud, security, infrastructure]
surfaces-at: [application-design, infrastructure-design]
related: [principle-of-least-privilege, rbac, secrets-management, zero-trust-security, terraform, kubernetes]
complexity: intermediate
---

# Cloud IAM

## What It Is
Identity and Access Management (IAM) in cloud platforms — the system that controls who (identity) can do what (permissions) on which resources (scope) in environments like AWS, GCP, and Azure. Cloud IAM is the foundational access control layer for all cloud resources: which service can read an S3 bucket, which engineer can deploy to production, which Lambda function can write to DynamoDB. Getting IAM right is both a security and operational necessity — overly permissive IAM is the most common vector for cloud breaches; overly restrictive IAM blocks legitimate operations and creates deployment friction.

## When to Apply
- Configuring any cloud-deployed service that interacts with other cloud resources
- Setting up CI/CD pipelines that deploy to cloud infrastructure
- Onboarding engineers with access to cloud environments
- Any time a service needs to access another cloud resource (database, queue, bucket, secret)
- Security reviews and audit preparation

## Key Concepts
- **AWS IAM Core Concepts**:
  - *Principals*: Who is making the request — IAM users (humans), IAM roles (services/automation), IAM groups (user collections), AWS services
  - *Policies*: JSON documents defining allowed/denied actions on resources. Attached to principals or resources
  - *Roles*: Identities that services assume — EC2 instances, Lambda functions, ECS tasks, CI/CD pipelines all authenticate via roles, not static credentials
  - *Actions*: API operations (`s3:GetObject`, `dynamodb:PutItem`, `ec2:DescribeInstances`)
  - *Resources*: ARNs specifying the target (`arn:aws:s3:::my-bucket/*`)

- **Principle of Least Privilege**: Grant only the minimum permissions required for the task. An API service that reads from S3 should have `s3:GetObject` on the specific bucket, not `s3:*` on `*`. Review and tighten permissions after initial deployment using IAM Access Analyzer and AWS IAM Last Used data

- **Instance/Task Roles (Not Static Credentials)**: Services should authenticate using IAM roles attached to the compute resource, not hardcoded access key/secret pairs. AWS SDKs automatically retrieve temporary credentials from the instance metadata service or ECS task metadata endpoint. This avoids credential rotation complexity and eliminates the risk of leaked long-lived credentials

- **Service Control Policies (SCPs)**: AWS Organizations feature that sets permission guardrails across all accounts. SCPs define the maximum permissions any entity in an account can have, regardless of individual role policies. Used to enforce organization-wide restrictions: "no resources outside us-east-1", "no disabling of CloudTrail"

- **Permission Boundaries**: IAM feature that limits the maximum permissions a role or user can have, even if their attached policies grant more. Used when delegating IAM administration — developers can create roles but cannot grant more permissions than their own permission boundary

- **Cross-Account Access**: IAM roles can be assumed across AWS accounts. Used for: CI/CD pipeline in one account deploying to another, centralized logging account, shared services. Role assumption uses `sts:AssumeRole` with trust policies defining who can assume the role

- **OIDC Federation for CI/CD**: Modern CI/CD (GitHub Actions, GitLab CI) can assume AWS roles using OpenID Connect (OIDC) federation without storing static AWS credentials. GitHub Actions requests a short-lived JWT from GitHub; AWS validates it and returns temporary credentials via STS. Eliminates static credentials in CI secrets entirely

- **GCP and Azure Equivalents**:
  - GCP: Service Accounts (roles attached to services), Workload Identity Federation (OIDC for CI/CD), IAM policies on resources
  - Azure: Managed Identities (equivalent to IAM roles), Azure RBAC roles, Entra ID (formerly Azure AD) for user identity

- **IAM as Code**: IAM policies and role definitions should be managed in Terraform or CloudFormation — not created via the console. This ensures auditability, review, and reproducibility

## In Practice
Method AWS deployments use IAM roles exclusively for service authentication — no static access keys for ECS tasks, Lambda functions, or EC2 instances. CI/CD pipelines authenticate via GitHub Actions OIDC federation. IAM roles are defined in Terraform with scoped resource ARNs. IAM Access Analyzer flags overly permissive policies. New environments default to a permission boundary that prevents privilege escalation. SCPs enforce cross-account guardrails in Method's AWS Organization.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Cloud IAM**: The most common cloud security incident is overly permissive IAM — `s3:*` on `*` is a data exfiltration waiting to happen. Use roles, not static credentials, for every service that runs in the cloud; the instance metadata service gives you automatic credential rotation for free. Define IAM policies in Terraform so they go through code review — IAM changes made via the console are invisible until something goes wrong. For CI/CD, OIDC federation eliminates the long-lived secret rotation problem entirely. Audit permissions quarterly with IAM Access Analyzer; the "last used" data shows you which permissions you can safely remove. → `engineering-knowledge-repository/cloud-iam.md`

## Related Entries
- [Principle of Least Privilege](principle-of-least-privilege.md) — cloud IAM is the primary mechanism for implementing least privilege in cloud environments
- [RBAC](rbac.md) — RBAC provides application-level authorization; cloud IAM provides infrastructure-level authorization
- [Secrets Management](secrets-management.md) — IAM roles replace static credentials for cloud service authentication; secrets management handles application-level secrets
- [Zero-Trust Security](zero-trust-security.md) — cloud IAM is a foundational component of zero-trust architecture
- [Terraform](terraform.md) — IAM roles and policies should be defined and managed as Terraform resources
- [Kubernetes](kubernetes.md) — Kubernetes service accounts map to cloud IAM roles via IRSA (IAM Roles for Service Accounts) on EKS

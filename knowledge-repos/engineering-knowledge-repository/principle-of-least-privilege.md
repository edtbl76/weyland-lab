---
id: principle-of-least-privilege
tags: [principle, security]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [zero-trust-security, rbac, oauth2-oidc, secrets-management]
complexity: foundational
---

# Principle of Least Privilege

## What It Is
A security principle stating that every user, service, or system component should have only the minimum permissions required to perform its specific function — and nothing more. Excess permissions expand the blast radius when credentials are compromised. Least privilege limits what an attacker can do if they gain access to any account or service.

## When to Apply
- IAM roles for cloud services — every Lambda function, ECS task, and EC2 instance should have a role that permits only what it needs
- Database access — application services should have read-only access unless they genuinely write; never `DBA` permissions for application accounts
- API authorizations — users should only see and modify resources they own or are explicitly authorized to access
- CI/CD pipelines — deployment pipelines should have the minimum permissions to deploy to the target environment
- User accounts — apply role-based access, regular reviews, immediate revocation on role change or departure

## When Not to Apply
- Never — least privilege is a universal principle, not a situational one. The question is always the degree of effort required to implement it correctly.

## Key Concepts
- **Permission Scope**: Define exactly what actions are needed — not "S3 full access" but `s3:GetObject` on specific bucket ARNs
- **IAM Role per Service**: Each service gets its own IAM role with only the permissions it needs — no shared roles between services
- **Wildcard Anti-Pattern**: `*` permissions (e.g., `"Action": "*"`) are almost never justified — they grant every permission including ones the service will never use
- **Permission Boundary**: AWS mechanism to set a maximum boundary on what permissions an IAM role or user can have — prevents privilege escalation
- **Time-Bound Access**: For elevated access needs (incident response, admin tasks), grant temporary elevated permissions rather than permanent elevated roles
- **Access Reviews**: Regularly audit who has what permissions — remove unnecessary permissions, deactivate unused accounts

## In Practice
Least privilege is Method's standard in all infrastructure engagements. In practice: start with no permissions and add only what the service needs (additive, not subtractive). Use AWS IAM Access Analyzer to identify over-privileged roles. For database access, create per-service users with minimal grants. For human access, use role-based access with regular reviews.

## Engineering Knowledge
💡 **Engineering Knowledge — Principle of Least Privilege**: Grant only the minimum permissions required. Every Lambda function gets its own IAM role with only the permissions it actually uses. No wildcard permissions, no admin credentials for application services. When a service is compromised, least privilege defines the blast radius — a service that can only read one S3 bucket can't exfiltrate your entire database. Start with no permissions; add only what's needed; review and prune regularly. → `engineering-knowledge-repository/security/principle-of-least-privilege.md`

## Related Entries
- [Zero Trust Security](zero-trust-security.md) — least privilege is a core operating principle of Zero Trust
- [RBAC](rbac.md) — role-based access control implements least privilege for user authorization
- [Secrets Management](secrets-management.md) — secrets managers implement least privilege for credential access

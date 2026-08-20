---
id: audit-logging
tags: [pattern, observability, security, backend]
surfaces-at: [nfr-requirements, infrastructure-design, functional-design]
related: [structured-logging, log-aggregation, secrets-management, rbac]
complexity: intermediate
---

# Audit Logging

## What It Is
An immutable record of who did what and when in a system — specifically capturing security-relevant and business-critical actions for compliance, forensics, and accountability. Audit logs differ from application logs: they record the *intent* and *outcome* of business operations (user logins, data access, permission changes, record modifications) rather than the technical execution detail. They must be tamper-evident and retained according to compliance requirements.

## When to Apply
- Systems processing personal data (GDPR, HIPAA, PCI-DSS compliance)
- Multi-user systems where accountability for data changes is required
- Financial and healthcare systems where every data access and modification must be traceable
- Any system where "who changed this record and when?" is a question you need to answer
- Security incident investigation — audit logs are the forensic record

## When Not to Apply
- High-volume, low-sensitivity operational events — these belong in regular application logs, not the audit log
- Developer-facing tooling without business data or security implications

## Key Concepts
- **Who**: The authenticated identity — user ID, service account, API client — not just a name
- **What**: The specific action — "READ customer record", "UPDATE account balance", "DELETE user"
- **When**: Precise timestamp (ISO 8601 with timezone)
- **Result**: Success or failure, and the reason for failure
- **Resource**: The specific record affected — resource type and ID
- **Immutability**: Audit logs must not be modifiable after write — use append-only storage (CloudTrail, write-once S3 buckets, dedicated audit log service)
- **Retention**: Define retention periods per compliance requirement — HIPAA typically requires 6 years, PCI-DSS 1 year hot + 1 year archive
- **Separation from Application Logs**: Audit logs should be stored separately from application logs — they have different retention, access control, and immutability requirements

## In Practice
Audit logging is a standard NFR in Method engagements for any system handling sensitive data. Implement as a cross-cutting concern — an audit event publisher called from service operations, not scattered inline calls. AWS CloudTrail provides audit logging for AWS API calls; application-level audit logging requires custom implementation. Store in append-only storage with restricted delete access.

## Engineering Knowledge
💡 **Engineering Knowledge — Audit Logging**: For any system with sensitive data, record who did what, when, and with what result — immutably. Audit logs answer compliance questions ("who accessed this patient record?") and forensic questions ("what did the attacker do after they got in?"). Separate from application logs — different retention, different access controls, append-only. Implement as a cross-cutting concern, not scattered throughout business logic. Define retention periods based on compliance requirements before building the system. → `engineering-knowledge-repository/observability/audit-logging.md`

## Related Entries
- [Structured Logging](structured-logging.md) — audit logs use structured format for queryability
- [Log Aggregation](log-aggregation.md) — audit logs are aggregated separately with stricter retention and access controls
- [RBAC](../security/rbac.md) — RBAC defines who can access what; audit logging records when they did

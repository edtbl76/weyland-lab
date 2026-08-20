---
id: autonomous-remediation
tags: [pattern, security, backend, infrastructure]
surfaces-at: [nfr-requirements, nfr-design, code-generation]
related: [security-hardening, security-testing, threat-modeling, defense-in-depth, incident-management, software-bill-of-materials]
complexity: advanced
---

# Autonomous Remediation

## What It Is
A security architecture pattern in which systems detect vulnerabilities or misconfigurations and automatically apply fixes — without requiring manual intervention for well-understood, low-risk remediation classes. Autonomous remediation closes the gap between vulnerability discovery and patch deployment, which is the primary bottleneck in modern security postures. The pattern distinguishes between detection (knowing a problem exists), triage (classifying risk and impact), and remediation (applying a fix) — and automates the full pipeline for pre-defined remediation playbooks. Human review gates remain mandatory for high-impact or novel remediation actions.

## When to Apply
- Applications managing large dependency graphs where CVE discovery outpaces manual patching capacity
- Cloud infrastructure with significant policy violations or misconfigurations surfaced by CSPM tools
- Any system where the remediation delay (time from discovery to patch deployment) creates unacceptable exposure windows
- CI/CD pipelines where security scanning is already integrated — remediation is the natural next step

## When Not to Apply
- Remediations that affect schema, data, or runtime behavior in production — human review required
- Novel or uncategorized vulnerability classes — autonomous action on unknown risk is dangerous
- Systems without rollback capability — never automate fixes you cannot undo

## Key Concepts
- **Remediation Playbooks**: Pre-defined, versioned sequences of actions for known fix patterns — dependency version bump, IAM policy restriction, security group rule removal, container base image update. Playbooks are the unit of autonomous execution; each must be reviewed and approved before deployment
- **Triage Gate**: Before any remediation executes, classify the finding: severity, confidence score, blast radius, rollback feasibility. Only pre-approved triage classes trigger autonomous execution; everything else routes to human review queue
- **Rollback-First Design**: Every remediation action must have a defined rollback path. If the fix cannot be automatically rolled back, it cannot be autonomously applied. This is a hard constraint
- **Dependency Auto-Patching**: Tools like Dependabot, Renovate, and Snyk automatically open PRs for dependency version bumps — the most mature form of autonomous remediation. Wire to auto-merge for low-risk patches (patch-version bumps passing tests) and require review for minor/major bumps
- **Infrastructure Drift Remediation**: Cloud CSPM tools (AWS Security Hub, Wiz, Prisma Cloud) detect policy violations. Automated remediation via Lambda functions or Step Functions can restore compliant state — e.g., closing public S3 buckets, removing overly permissive IAM policies, enforcing encryption at rest
- **SBOM-Driven Remediation**: A live Software Bill of Materials (SBOM) enables continuous vulnerability matching — when a new CVE is published, the SBOM is queried to determine affected components and trigger the appropriate remediation playbook. See Software Bill of Materials entry
- **Human-in-the-Loop Escalation**: Remediations outside pre-approved playbooks, or where confidence is below threshold, automatically escalate to human review with full context — finding, proposed fix, blast radius, rollback plan
- **Audit Trail**: Every autonomous remediation action must be logged with timestamp, triggering event, playbook executed, system state before and after, and operator who approved the playbook. Non-negotiable for compliance contexts

## In Practice
Method implements autonomous remediation in tiers: Tier 1 (fully automated, auto-merged) for dependency patch bumps and known infrastructure misconfigurations; Tier 2 (automated PR + test, human merge) for minor version bumps and security group changes; Tier 3 (automated analysis + human decision) for major version bumps, logic-touching changes, and novel CVEs. Dependabot or Renovate handles Tier 1/2 dependency remediation. AWS Security Hub + EventBridge + Lambda handles Tier 1 infrastructure remediation. All actions are logged in CloudTrail and surfaced in the security observability dashboard.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Autonomous Remediation**: Detection without remediation is a bottleneck — the real security metric is time-to-patch, not time-to-detect. Structure remediation as tiered playbooks: auto-merge patch bumps that pass tests, require human review for minor/major version changes, always require approval for logic-touching fixes. Every playbook needs a rollback path — if it can't be undone, it can't be automated. Wire SBOM to CVE feeds so new vulnerability disclosures immediately trigger remediation workflows against your actual component inventory. Log every automated action with full context — autonomous remediation without audit trail is a compliance violation. → `engineering-knowledge-repository/autonomous-remediation.md`

## Related Entries
- [Security Hardening](security-hardening.md) — hardening reduces the attack surface that remediation must defend
- [Security Testing](security-testing.md) — vulnerability discovery is the upstream trigger for remediation pipelines
- [Threat Modeling](threat-modeling.md) — threat models determine which remediation classes require human review vs. can be automated
- [Defense in Depth](defense-in-depth.md) — autonomous remediation is one layer in a defense-in-depth security strategy
- [Incident Management](incident-management.md) — remediations that fail or cause regression escalate to the incident management process
- [Software Bill of Materials](software-bill-of-materials.md) — live SBOM is the component inventory that drives CVE-to-component matching in remediation pipelines

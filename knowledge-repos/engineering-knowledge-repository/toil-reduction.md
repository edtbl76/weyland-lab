---
id: toil-reduction
tags: [methodology, reliability, team-practices]
surfaces-at: [application-design, infrastructure-design]
related: [site-reliability-engineering, incident-management, on-call-management, infrastructure-as-code, ci-cd]
complexity: intermediate
---

# Toil Reduction

## What It Is
The SRE practice of identifying and eliminating "toil" — repetitive, manual, automatable operational work that scales with service load and provides no lasting value. Toil is characterized by being manual (requires human execution), repetitive (done over and over), automatable (could be done by a machine), tactical (reactive, not strategic), and devoid of enduring value (completing the task leaves no lasting improvement). Google SRE defines a target of keeping toil below 50% of engineering time, with the remainder devoted to engineering work that reduces future toil.

## When to Apply
- When the team spends significant time on repetitive operational tasks
- When on-call involves manual steps that happen on every incident
- When deployments, database migrations, or other processes require repeated manual intervention
- When the team is growing and manual processes are not scaling

## Key Concepts
- **Identifying Toil**: Common sources:
  - Manual deployments (clicking through a UI to deploy rather than running a command)
  - Recurring on-call tasks that always involve the same steps (e.g., restarting a service every Tuesday)
  - Manual data fixes and one-off database operations run on a schedule
  - Manually rotating credentials or updating configuration values
  - Manually reviewing and approving low-risk, high-frequency changes
  - Manual report generation and distribution
- **Toil vs. Overhead vs. Engineering Work**:
  - *Toil*: Repetitive, manual, scales with load. Target for elimination
  - *Overhead*: Necessary but non-toil: meetings, 1:1s, planning. Can be minimized but not eliminated
  - *Engineering work*: Reduces future toil, adds capabilities, improves reliability. Should be maximized
- **Automation Strategies**:
  - *Runbooks → Scripts*: If a runbook says "run these 5 commands in order," write a script. If that script is run repeatedly, integrate it into a CI/CD pipeline
  - *Escalation automation*: Auto-remediation scripts that run on certain alert conditions (restart a failed pod, clear a disk)
  - *Self-service platforms*: Internal developer platforms where teams can provision resources, rotate credentials, or create environments without waiting on another team
  - *GitOps*: Infrastructure changes via PR rather than manual console operations. Auditable; repeatable; no manual steps
- **Toil Accounting**: Measure how much engineering time is spent on toil per sprint or week. Classify tickets as toil vs. engineering work. Track the trend — if toil percentage is increasing, the engineering practice is not keeping up with growth
- **Auto-Remediation**: Automated responses to common operational conditions — restart a pod if it fails a liveness probe, scale out if CPU exceeds 80%, clear a queue backlog if it grows too large. Reduces the need for human intervention on predictable, well-understood conditions
- **Eliminate Before Automating**: The best toil reduction is eliminating the need for the task entirely. Before automating a manual step, ask whether the step is necessary. Manual approval gates for low-risk changes that always get approved are a candidate for removal, not automation

## In Practice
Method tracks toil percentage per team per sprint. On-call runbooks are automated as scripts when they are executed more than twice without changes. Self-service internal tooling covers environment provisioning, credential rotation, and deployment without requiring platform team intervention. Auto-remediation handles pod restarts, disk cleanup, and queue drain for well-understood failure modes. Toil reduction is a standing item in sprint retrospectives.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Toil Reduction**: If you're running the same runbook steps more than twice, write a script. If you're running that script more than weekly, automate it into a pipeline. Toil compounds: as traffic and team size grow, un-automated processes consume an ever-increasing fraction of engineering time. The 50% toil ceiling from Google SRE is a practical guideline — teams spending > 50% of their time on operational tasks are not investing in the reliability improvements that would reduce that toil. Auto-remediation is the highest-leverage toil reduction: fix predictable failures automatically at 3am instead of paging the on-call engineer. → `engineering-knowledge-repository/toil-reduction.md`

## Related Entries
- [Site Reliability Engineering](site-reliability-engineering.md) — toil reduction is a defining SRE discipline; the 50% toil budget comes from Google SRE
- [Incident Management](incident-management.md) — recurring incidents generate toil; post-mortems should identify toil reduction opportunities
- [On-Call Management](on-call-management.md) — toil shows up most visibly as repeated on-call interruptions for automatable tasks
- [Infrastructure as Code](infrastructure-as-code.md) — IaC eliminates the toil of manual infrastructure provisioning and configuration
- [CI/CD](ci-cd.md) — CI/CD pipelines automate the toil of manual build, test, and deployment processes

---
id: incident-management
tags: [methodology, observability, reliability, team-practices]
surfaces-at: [infrastructure-design, application-design]
related: [on-call-management, site-reliability-engineering, service-level-objectives, error-budgets]
complexity: intermediate
---

# Incident Management

## What It Is
The structured process for detecting, responding to, communicating about, and learning from production incidents. An incident is any unplanned disruption that affects users or violates SLOs — from a brief spike in error rates to a full service outage. Effective incident management minimizes customer impact through fast detection and resolution, maintains stakeholder communication throughout, and generates organizational learning through blameless post-mortems. Without a defined process, incident response is improvised under pressure — slower resolution, worse communication, and repeated incidents.

## When to Apply
- Every team operating production services with user impact
- Before launching a service to production (define the process, don't improvise it during the first incident)
- After any significant incident (retrospective on whether the process worked)
- When incident resolution times are high or post-incident learning is not happening

## Key Concepts
- **Incident Severity Levels**: Define severity before incidents happen, not during them:
  - *SEV-1 / P1*: Complete service outage or data loss. All hands. Immediate executive notification
  - *SEV-2 / P2*: Major feature degradation affecting significant user population. On-call lead + engineer
  - *SEV-3 / P3*: Minor degradation with workaround available. On-call engineer handles
  - *SEV-4 / P4*: Cosmetic or non-user-impacting issue. Normal ticket workflow
- **Incident Roles**:
  - *Incident Commander (IC)*: Coordinates the response; keeps others from working in silos; makes go/no-go decisions. Does NOT do hands-on debugging — their job is coordination
  - *Technical Lead*: Leads the technical investigation. Delegates tasks; reports findings to IC
  - *Communications Lead*: Drafts status page updates, stakeholder messages, and Slack communications. Frees the technical team from communication overhead
  - *Scribe*: Documents the timeline in real-time — what was tried, what was found, what was changed. Invaluable for post-mortems
- **Incident Communication**:
  - Status page updates (every 15-30 minutes during active incidents) for external users
  - Stakeholder Slack channel for internal communication
  - Use templated language: "We are investigating an issue affecting [service]. [X% of users] are impacted. Our team is working to resolve this and will provide an update by [time]."
  - Communicate early and often, even when there's nothing new — silence is worse than "still investigating"
- **War Room / Incident Channel**: Create a dedicated Slack channel for each incident (e.g., `#inc-2024-01-15-checkout`). All incident discussion, decisions, and findings go there. Prevents signal from being lost in general channels
- **Resolution Criteria**: Define what "resolved" means before closing — not just "metrics are back to normal" but "root cause is identified, mitigation is in place, and the service is stable for at least 30 minutes"
- **Blameless Post-Mortem**: After every SEV-1/2 (and optionally SEV-3), conduct a post-mortem focused on systemic causes, not individual blame. Questions: What happened? What was the timeline? What was the impact? What went well? What went poorly? What action items will prevent recurrence?
  - Blameless means: the system failed, not the person. People made reasonable decisions given the information they had at the time
  - Post-mortem within 48-72 hours while memory is fresh
  - Action items must be assigned with owners and deadlines — post-mortems without action items are ceremony
- **Runbooks**: Pre-written diagnostic and remediation procedures for common failure scenarios. Linked from alert definitions. The on-call engineer should find a runbook for common pages; novel incidents justify improvisation
- **Incident Tracking**: Log all incidents in a system of record (Jira, Linear, PagerDuty) with severity, duration, impact, and post-mortem link. Track MTTA and MTTR. Review monthly for patterns

## In Practice
Method uses a defined incident severity framework and PagerDuty for incident alerting. SEV-1/2 incidents trigger an automatic incident Slack channel and a Zoom bridge. Incident Commander role rotates with the on-call rotation. Status page updates are sent every 20 minutes during active incidents via Statuspage.io. Post-mortems are required within 72 hours for SEV-1/2; completed in Confluence with action items tracked in Jira. MTTR is reviewed monthly as an SRE health metric.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Incident Management**: Define your incident process before your first incident — improvised coordination under pressure produces slower resolution and worse communication. The Incident Commander role is critical: separating coordination from technical investigation is what prevents the "everyone looking at everything" chaos. Blameless post-mortems are where organizational learning happens — a post-mortem that blames an individual produces no systemic improvement and discourages future transparency. Track MTTR over time; a rising MTTR is a signal of accumulating technical debt or alert quality degradation. → `engineering-knowledge-repository/incident-management.md`

## Related Entries
- [On-Call Management](on-call-management.md) — on-call is the first-response layer for detected incidents
- [Site Reliability Engineering](site-reliability-engineering.md) — incident management is a core SRE discipline
- [Service Level Objectives](service-level-objectives.md) — SLO breaches are the primary trigger for incident declaration
- [Error Budgets](error-budgets.md) — incidents consume error budget; high incident rates signal reliability work is needed

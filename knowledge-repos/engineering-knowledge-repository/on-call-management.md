---
id: on-call-management
tags: [methodology, observability, reliability, team-practices]
surfaces-at: [infrastructure-design, application-design]
related: [incident-management, site-reliability-engineering, alerting-fatigue, service-level-objectives, metrics-and-alerting]
complexity: intermediate
---

# On-Call Management

## What It Is
The practices, tooling, and policies for ensuring that production incidents are detected, routed to the right engineer, and resolved with minimal disruption — including how on-call rotations are structured, how alerts escalate, and how to keep on-call sustainable over time. On-call is a contract between the team and the systems they operate: the team commits to responding to production issues; the systems (and the team's practices) must be designed to make that response manageable. Unsustainable on-call is one of the leading causes of engineer burnout and attrition.

## When to Apply
- Any team operating production systems that affect users
- Before launching a new service to production
- When alert volume is causing burnout or engineers are silencing pages
- When establishing SLAs that require response time commitments

## Key Concepts
- **On-Call Rotation**: A schedule defining who is responsible for responding to production incidents at any given time. Typically one primary and one secondary (backup). Rotations should spread burden across the team — weekly rotations are common; avoid consecutive weeks for the same person
- **Escalation Policies**: Define what happens when the primary doesn't acknowledge within N minutes: alert the secondary; then escalate to a team lead; then escalate to a manager. Escalation policy ensures incidents are never silently dropped
- **Tools**:
  - *PagerDuty*: The enterprise standard. Rich escalation policies, on-call scheduling, alert routing, incident lifecycle management, and integrations with Datadog, CloudWatch, and Grafana
  - *OpsGenie (Atlassian)*: Similar to PagerDuty; integrated with Jira and Confluence. Good for Atlassian-heavy teams
  - *Grafana OnCall*: Open-source; integrates natively with Grafana alerting. Lower cost option
  - *Opsgenie, VictorOps (Splunk)*: Other alternatives with similar feature sets
- **Alert Routing**: Route alerts to the appropriate on-call team based on service ownership. Alerts for the payments service go to the payments team's rotation; don't route all alerts to one shared rotation. Teams own what they operate
- **Handoff Notes**: At the end of each on-call shift, the outgoing engineer writes a brief summary: which alerts fired, what was investigated, what is still open, what needs follow-up. Prevents knowledge loss between rotations
- **Runbooks**: For each common alert, there should be a runbook — a documented procedure for diagnosing and resolving the issue. A runbook transforms a 3am "what do I do?" panic into a checklist. Link runbooks directly from alert definitions so the on-call engineer sees the link in the notification
- **Sustainable On-Call**:
  - Alert quality matters more than alert quantity — every alert should be actionable. Non-actionable alerts must be fixed or removed (see [Alerting Fatigue](alerting-fatigue.md))
  - Limit interruptions — fewer than 2-3 pages per shift is a reasonable target
  - Compensate on-call engineers fairly (time off in lieu, on-call pay)
  - Rotate fairly — no single engineer should carry disproportionate on-call burden
  - Track on-call burden metrics: interruptions per shift, MTTA (mean time to acknowledge), MTTR (mean time to resolve)
- **On-Call Onboarding**: New engineers should shadow the on-call rotation before being added as primary. Don't put a new hire on-call solo in their first month

## In Practice
Method uses PagerDuty for all on-call management. Each team owns a dedicated escalation policy with 5-minute primary acknowledgment SLA before escalating to secondary. Weekly rotations with minimum team size of 4 before adding on-call responsibility. Each alert definition links to a runbook in Confluence. On-call load is reviewed monthly — alerts with zero runbook link or > 5 firings per week without resolution are flagged for remediation.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — On-Call Management**: On-call is unsustainable when alert quality is poor — fix alerts, not engineers' tolerance for noise. Every alert must have a runbook; an alert without a runbook is just a notification that something might be wrong. Set up escalation policies before you go live in production — a production incident at 2am with no escalation path and no one responding is a business incident. Track on-call burden per engineer and use it as an input to engineering capacity planning. Distribute on-call fairly; if one team member is taking 80% of the pages, something structural is wrong. → `engineering-knowledge-repository/on-call-management.md`

## Related Entries
- [Incident Management](incident-management.md) — on-call is the trigger for the incident management process
- [Site Reliability Engineering](site-reliability-engineering.md) — SRE practices define on-call standards and sustainability targets
- [Alerting Fatigue](alerting-fatigue.md) — alert quality is the primary determinant of on-call sustainability
- [Service Level Objectives](service-level-objectives.md) — SLOs define the conditions that trigger on-call response
- [Metrics and Alerting](metrics-and-alerting.md) — alerting infrastructure routes notifications to on-call tooling

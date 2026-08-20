---
id: on-call-practices
tags: [methodology, team-practices, reliability]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [blameless-postmortems, site-reliability-engineering, alerting-fatigue, service-level-objectives]
complexity: intermediate
---

# On-Call Practices

## What It Is
The processes, tooling, and cultural norms that govern who responds to production incidents, how they respond, and how the organization learns from those incidents. Good on-call practices balance reliability (incidents are caught and resolved quickly) with engineer sustainability (on-call doesn't burn people out). The key elements: clear escalation paths, comprehensive runbooks, fair rotation, and continuous improvement from each incident.

## When to Apply
- Any team running production software with users
- Before the first production launch — establish on-call infrastructure as part of Iteration 0
- When on-call is causing engineer attrition or burnout — diagnose and improve the practices

## When Not to Apply
- Prototype systems with no users and no uptime expectation

## Key Concepts
- **Rotation**: On-call responsibility rotates fairly across the team — no single person permanently bears the burden. Common patterns: weekly rotation, follow-the-sun for global teams.
- **Primary / Secondary**: A primary on-call engineer handles pages; a secondary is backup if primary is unavailable. Reduces single point of failure.
- **Escalation Policy**: Documented who to escalate to when the on-call engineer can't resolve — by severity and by technical domain
- **Runbooks**: Step-by-step instructions for common incidents — what the on-call engineer should do for each alert. Reduces decision fatigue and inconsistency.
- **Toil Reduction**: If the same runbook steps are executed manually every week, that's toil — automate it and remove the alert
- **On-Call Compensation**: Teams that receive out-of-hours pages should be compensated appropriately — either time back or financial compensation
- **Shadow On-Call**: New engineers shadow an experienced on-call before taking primary — builds confidence and knowledge transfer
- **Handoff Notes**: Before going off rotation, document open investigations, changes in flight, and elevated risk areas for the incoming on-call

## In Practice
On-call practices are established in Iteration 0 at Method alongside observability and alerting. PagerDuty or OpsGenie is the standard alerting/rotation tool. Runbooks live in the repository alongside code — updated when alerts are created or modified. Monthly postmortems review alert volume and quality.

## Engineering Knowledge
💡 **Engineering Knowledge — On-Call Practices**: Production reliability requires someone awake when it breaks. Make on-call sustainable: fair rotation, clear escalation, runbooks for every alert (on-call shouldn't improvise at 2am), and active toil reduction. The best on-call engineering is eliminating the pages through automation and better systems. Establish the rotation, alerting, and runbook structure before the first production deploy — not after the first incident. → `engineering-knowledge-repository/team-practices/on-call-practices.md`

## Related Entries
- [Blameless Postmortems](blameless-postmortems.md) — postmortems improve system reliability and reduce on-call burden
- [Alerting Fatigue](../observability/alerting-fatigue.md) — high alert noise directly degrades on-call quality and sustainability
- [Site Reliability Engineering](../methodologies/site-reliability-engineering.md) — SRE provides the framework for sustainable on-call practices

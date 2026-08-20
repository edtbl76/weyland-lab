---
id: blameless-postmortems
tags: [methodology, team-practices, reliability]
surfaces-at: [requirements-analysis]
related: [site-reliability-engineering, on-call-practices, four-key-metrics]
complexity: foundational
---

# Blameless Postmortems

## What It Is
A structured process for reviewing incidents and failures with the explicit goal of learning and systemic improvement — not assigning individual blame. The premise: most failures are caused by systemic issues (unclear processes, missing safeguards, inadequate tooling) that reasonable people encounter, not by individual carelessness or malice. Punishing individuals for systemic failures prevents honest reporting and destroys the safety required for learning.

## When to Apply
- After every significant production incident, outage, or near-miss
- After a deployment that caused degradation, even if quickly rolled back
- After any event that significantly affected users, revenue, or SLO compliance
- When the same type of failure is recurring — investigate root causes systemically

## When Not to Apply
- Do not skip postmortems for "minor" incidents — patterns in small incidents predict large failures
- Gross negligence or deliberate misuse are exceptions — these require different processes, not postmortems

## Key Concepts
- **Blameless**: The postmortem focuses on systems, processes, and conditions — not on individuals. "What conditions made this failure possible?" not "who caused this?"
- **Timeline**: A factual reconstruction of the incident — what happened and when, without interpretation
- **Contributing Factors**: The conditions that made the failure possible — not "root cause" (rarely one) but the chain of contributing factors
- **Action Items**: Concrete, assigned, time-boxed improvements that reduce the likelihood or impact of recurrence
- **Five Whys**: An iterative technique for identifying contributing factors — ask "why?" five times to trace from symptom to systemic cause
- **Psychological Safety**: The cultural prerequisite — engineers must believe that reporting honestly won't result in punishment; otherwise postmortems produce sanitized non-learning

## In Practice
Blameless postmortems are a Method recommendation for all client production systems. The template structure: incident summary → timeline → user impact → contributing factors → what went well → action items. Share postmortems broadly — transparency accelerates organizational learning and signals that failures are treated as systemic problems. Action items that never close are a sign that the process has no teeth — track them.

## Engineering Knowledge
💡 **Engineering Knowledge — Blameless Postmortems**: After every significant incident, ask "what conditions made this possible?" — not "who did this?" Blame prevents honest reporting; honest reporting is what produces learning. Document the timeline, contributing factors, and concrete action items. Share the postmortem broadly — transparency and organizational learning are the whole point. Postmortems without closed action items are theater. Psychological safety is the cultural prerequisite. → `engineering-knowledge-repository/team-practices/blameless-postmortems.md`

## Related Entries
- [Site Reliability Engineering](../methodologies/site-reliability-engineering.md) — blameless postmortems are a core SRE cultural practice
- [On-Call Practices](on-call-practices.md) — on-call engineers are the first responders whose experience informs postmortems

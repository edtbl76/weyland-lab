---
id: contextual-inquiry
tags: [discovery]
surfaces-at: [requirements-analysis, validated-intent]
related: [customer-journey-mapping, service-blueprinting, jobs-to-be-done-research, double-diamond, affinity-mapping]
complexity: intermediate
---

# Contextual Inquiry

## What It Is
A field research method developed by Hugh Beyer and Karen Holtzblatt (part of the Contextual Design methodology) in which researchers observe and interview users in their natural work environment while they perform actual tasks — rather than bringing them into a lab or asking them to recall behavior after the fact. Contextual inquiry combines observation and semi-structured interview: the researcher watches the user work, asks questions in the moment ("why did you do that?"), and captures the actual workflow including workarounds, unofficial tools, and tacit knowledge that users would never think to mention in a conference room interview. The output is ground-truth insight into how work is actually done, not how it's supposed to be done.

## When to Use
- When user research needs to go beyond what users say they do to reveal what they actually do
- Discovering workarounds, shadow IT, and informal processes that will break if not accounted for
- Before redesigning a complex workflow: understanding the current-state process in operational depth
- Requirements for back-office or operations systems where user tasks are complex and context-dependent
- When stakeholders' description of user behavior doesn't match what users report in usability testing

## Key Concepts
- **The Four Principles**: Contextual inquiry is structured around four principles — Context (research in the actual work environment), Partnership (researcher and user work as co-interpreters of the work), Interpretation (researcher checks understanding in real time), Focus (the inquiry has a research focus that guides but doesn't constrain what is observed)
- **Master-Apprentice Model**: The researcher adopts the mindset of a new apprentice learning from an expert master — curious, observational, non-judgmental. This posture elicits more authentic behavior than "expert evaluating user"
- **In Situ Observation**: Being in the actual environment reveals context that no interview captures: the three monitors, the paper notebook next to the keyboard, the colleague they ask every time a certain case type comes in. These are requirements evidence
- **Workarounds as Requirements**: Every workaround observed is an unmet requirement. If users copy-paste data between systems, that's an integration requirement. If they keep a personal spreadsheet to track cases, that's a case management feature gap
- **Interpretation Sessions**: After field visits, the research team conducts interpretation sessions — structured debriefs where field notes are shared, insights captured on affinity notes, and observations synthesized. The interpretation session is where raw observation becomes design insight
- **Sample Size**: Contextual inquiry typically requires 8-15 users across representative roles to reach saturation — where new observations stop producing new insights. Fewer than 6 users is rarely sufficient for confident synthesis
- **Contrast with Surveys and Focus Groups**: Surveys capture stated behavior at scale; focus groups capture group opinion. Neither reveals tacit knowledge, workarounds, or the context that explains behavior. Contextual inquiry fills that gap at smaller scale

## Method Application
Method uses contextual inquiry in discovery phases for systems that support complex operational work — claims processing, field service, supply chain operations, clinical workflows. These are environments where users have developed sophisticated adaptations that standard interviews won't surface. A week of contextual inquiry in a client's operations center produces requirements evidence that months of stakeholder interviews cannot.

## Consulting Insight
🎯 **Consulting Tool — Contextual Inquiry**: The most valuable product of a contextual inquiry session is not the insight notes — it's the moment a stakeholder joins a session and watches a user work. When a VP of Operations observes a claims adjuster running four systems simultaneously and cross-referencing a printed checklist because the system can't show all the information on one screen, the requirements conversation changes permanently. Whenever possible, bring decision-makers into the field. → `consulting-tools-repository/contextual-inquiry.md`

## Related Entries
- [Customer Journey Mapping](customer-journey-mapping.md) — contextual inquiry produces the evidence that makes journey maps accurate; observations map to journey stages
- [Service Blueprinting](service-blueprinting.md) — backstage observations from contextual inquiry populate the backstage swim lane of the blueprint
- [Jobs to Be Done Research](jobs-to-be-done-research.md) — JTBD interviews surface motivation and context; contextual inquiry observes the task execution
- [Double Diamond](double-diamond.md) — contextual inquiry is a primary Discover-phase research method
- [Affinity Mapping](affinity-mapping.md) — interpretation sessions from contextual inquiry produce the observation notes that are synthesized through affinity mapping

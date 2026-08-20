---
id: risk-register
tags: [delivery, organizational]
surfaces-at: [validated-intent, workflow-planning]
related: [dependency-mapping, iron-triangle, stakeholder-mapping, raci, cynefin]
complexity: foundational
---

# Risk Register

## What It Is
A structured artifact that captures, categorizes, and tracks the risks facing a program — recording each risk's description, probability, impact, risk score, owner, and response plan. The risk register is both a documentation tool (what risks exist) and a management tool (what is being done about them). It is a living artifact — updated regularly throughout the program as new risks emerge, existing risks materialize or are resolved, and risk responses are executed. In consulting programs, the risk register surfaces risks not only to delivery (schedule, cost, scope) but to business outcomes (adoption, regulatory, organizational, and vendor risks).

## When to Use
- Program kickoff: establish baseline risk inventory before work begins
- Weekly program governance: review and update risk status
- When a program is showing signs of distress — retrospective risk analysis identifies what was missed
- Technical due diligence: risk register is a primary output
- Stakeholder communication: risk register provides transparent visibility to program health

## Key Concepts
- **Risk vs. Issue**: A risk is a potential future event that may harm the program; an issue is a risk that has materialized and is currently causing harm. Risk registers should track both, with clear separation — issues require immediate response; risks require monitoring and mitigation
- **Risk Dimensions**:
  - *Probability*: Likelihood the risk will occur (High / Medium / Low, or 1-5 scale)
  - *Impact*: Effect on the program if the risk occurs (High / Medium / Low, or 1-5 scale)
  - *Risk Score*: Probability × Impact. Prioritizes risks for attention
- **Risk Categories**: Common categories for technology programs — Technical (architecture, integration, performance), Organizational (change resistance, capacity, stakeholder), External (vendor, regulatory, market), Schedule (dependencies, resource availability), Commercial (contract, IP, compliance)
- **Risk Response Strategies**:
  - *Avoid*: Change the plan to eliminate the risk entirely
  - *Mitigate*: Take action to reduce probability or impact before the risk occurs
  - *Transfer*: Shift the risk to another party (insurance, vendor contract, client)
  - *Accept*: Acknowledge and monitor without active response; often appropriate for low-probability/low-impact risks
- **Risk Owner**: Each risk must have a single named owner accountable for monitoring and executing the response plan. Unowned risks are ignored risks
- **RAID Log**: Risk registers are often part of a RAID Log — Risks, Assumptions, Issues, Dependencies. This provides a single governance artifact for the four primary program hazard types
- **Escalation Thresholds**: Risks above a certain score should trigger automatic escalation — to Program Management, to the client, or to leadership. Define thresholds at kickoff, not after a crisis
- **Red-Amber-Green (RAG) Status**: Risk registers typically use RAG status for overall program health and individual risk status — Red (critical, requires immediate action), Amber (elevated, requires monitoring), Green (within acceptable range)

## Method Application
Method maintains a risk register for every engagement from kickoff through close. The register is reviewed at every weekly program status meeting and at every formal governance review. Risks that have been sitting Amber for more than two weeks without response movement are escalated. The risk register is also the primary input to the program's contingency planning — what are the scenarios we must be prepared to respond to?

## Consulting Insight
🎯 **Consulting Tool — Risk Register**: The most important risk register behavior is not capturing risks — it's actively closing them. A register that grows every week but never shrinks is a documentation exercise, not a risk management practice. At every review, ask: what risks have been resolved this week? What responses were executed? What probability or impact changed? A well-managed register should show risk scores trending down over time as mitigations take effect. A register that only grows is a red flag about program health, not a measure of due diligence. → `consulting-tools-repository/risk-register.md`

## Related Entries
- [Dependency Mapping](dependency-mapping.md) — high-risk dependencies are direct inputs to the risk register; dependency map and risk register should be maintained together
- [Iron Triangle](iron-triangle.md) — risks are threats to one or more triangle vertices; risk scores should be assessed against schedule, scope, and cost impact
- [Stakeholder Mapping](stakeholder-mapping.md) — high-influence resisters in the stakeholder map are direct inputs to organizational risk categories
- [RACI](raci.md) — each risk must have a named owner; RACI ensures accountability for risk response
- [Cynefin Framework](cynefin.md) — risk types differ by Cynefin domain: known risks (Complicated), emergent risks (Complex), existential risks (Chaotic)

---
id: assumption-mapping
tags: [facilitation, discovery, product]
surfaces-at: [requirements-analysis, validated-intent]
related: [lean-startup, opportunity-solution-tree, dot-voting, impact-effort-matrix, design-sprint]
complexity: intermediate
---

# Assumption Mapping

## What It Is
A structured facilitation technique that surfaces and prioritizes the assumptions underlying a product, strategy, or program decision — enabling teams to identify which assumptions must be validated before committing to a path. Developed in the context of lean startup and continuous discovery practice, assumption mapping places assumptions on a 2×2 grid with Importance (critical to success / not critical) on the vertical axis and Certainty (evidence exists / no evidence) on the horizontal axis. Assumptions that are both critical and uncertain are the highest priority to test. The technique prevents teams from building on unvalidated foundations — particularly the assumption that users want what the team is building.

## When to Use
- Before committing to a product investment or solution direction
- When a team is about to start delivery on something with significant unvalidated assumptions
- Discovery kickoff: what must be true for this initiative to succeed?
- Risk identification: uncertain assumptions are risks; certain assumptions are validated constraints
- Before a Design Sprint: what are we trying to learn by Friday?

## Key Concepts
- **What is an Assumption?**: Any belief about customers, the market, the technology, the organization, or the business model that has not been confirmed with evidence. "Users will find this valuable," "this API will support the required throughput," "the sales team will adopt this tool" — all assumptions until validated
- **The 2×2 Grid**:
  - *Critical / Uncertain (top-right)*: Must-test assumptions — the program's success hinges on these, and we have no evidence. These are the riskiest. Test immediately
  - *Critical / Certain (top-left)*: Validated foundations — important and supported by evidence. These are the safe bets
  - *Not Critical / Uncertain (bottom-right)*: Interesting to test, but not blocking. Monitor
  - *Not Critical / Certain (bottom-left)*: Known and unimportant. Don't invest research here
- **Assumption Types**:
  - *Desirability*: Do users want this? Will they change behavior?
  - *Feasibility*: Can we build it? Does the technology support it?
  - *Viability*: Is there a business model? Does the unit economics work?
  - *Usability*: Can users accomplish the task with this interface or workflow?
- **Assumption Generation**: Run a divergent phase first — each participant writes all the assumptions they can identify (positive and negative) before grouping and discussion. Combined with dot voting to prioritize which quadrant items are most critical
- **Test Cards**: For each critical/uncertain assumption, write a test card: "We believe [assumption]. To validate this, we will [experiment]. We will know this is validated when [measurable outcome]." Test cards convert assumptions into lean experiments
- **Assumption Mapping vs. Risk Register**: The risk register tracks events that may harm the program; assumption mapping surfaces beliefs that may be wrong. They overlap — a critical/uncertain assumption is a risk — but the framing is different: risk is threat-oriented, assumption mapping is validation-oriented

## Method Application
Method runs assumption mapping at the start of discovery phases and before major solution commitments. The output identifies which assumptions need validation experiments (lean startup BML cycles, user interviews, prototypes, data analysis) before the full program investment is confirmed. This prevents the most expensive discovery failure: learning after six months of delivery that the core premise was wrong.

## Consulting Insight
🎯 **Consulting Tool — Assumption Mapping**: The most valuable assumption to surface is the one the team considers most obvious. "Of course users will adopt this — our internal research showed 80% interest." That 80% interest figure from an internal survey of people who were told to be interested is not evidence; it's an artifact of the survey design. Mapping it as an assumption — rather than a fact — puts it in the critical/uncertain quadrant where it belongs and triggers the validation work that would have been skipped. The assumptions teams resist mapping are usually the ones that most need to be tested. → `consulting-tools-repository/assumption-mapping.md`

## Related Entries
- [Lean Startup](lean-startup.md) — assumption mapping identifies which assumptions to test; lean startup's BML loop is the testing mechanism
- [Opportunity Solution Tree](opportunity-solution-tree.md) — OST experiments test the assumptions underlying solution nodes; assumption mapping identifies which OST assumptions are most critical
- [Dot Voting](dot-voting.md) — dot voting can prioritize which assumptions the group considers most critical before positioning them on the 2×2
- [Impact-Effort Matrix](impact-effort-matrix.md) — the 2×2 structure of assumption mapping mirrors the impact-effort matrix; both use visual positioning to surface prioritization conversations
- [Design Sprint](design-sprint.md) — the sprint question ("what do we want to learn by Friday?") is answered by identifying the critical/uncertain assumption that the prototype will test

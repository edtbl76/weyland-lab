---
id: decision-matrix
tags: [delivery, facilitation, strategy]
surfaces-at: [validated-intent, requirements-analysis, workflow-planning]
related: [iron-triangle, risk-register, moscow-prioritization, rice-scoring, build-buy-partner]
complexity: foundational
---

# Decision Matrix (Weighted Scoring Matrix)

## What It Is
A structured evaluation tool that scores multiple options against a set of criteria, with each criterion weighted by importance, to produce a ranked comparison. Also called a weighted scoring matrix, criteria matrix, or Pugh matrix. The decision matrix converts subjective multi-criteria decisions into a traceable, defensible analysis — making the basis for a recommendation visible and auditable. It is used in technology vendor selection, architecture option analysis, prioritization decisions, and any situation where multiple options must be evaluated against multiple competing criteria.

## When to Use
- Technology vendor or platform selection: comparing vendors across functional, technical, and commercial criteria
- Architecture option analysis: comparing two or more architectural approaches
- When a decision requires multi-criteria comparison and the team is divided
- Documenting the basis for a recommendation that will be presented to executive stakeholders
- Build/buy/partner decisions: structured scoring when the qualitative arguments are balanced

## Key Concepts
- **Criteria Definition**: The most important step — selecting the right criteria. Criteria should reflect actual decision requirements, not implicit preferences for a pre-selected option. Common pitfalls: too many criteria (dilutes signal), criteria that all point the same direction (confirms bias rather than evaluates trade-offs)
- **Weighting**: Each criterion is assigned a weight reflecting its relative importance (typically summing to 100% or 10). Weighting forces explicit prioritization — which criteria matter most? — and allows the same raw scores to produce different results for different strategic contexts
- **Scoring**: Each option is scored on each criterion (typically 1-5 or 1-10). Scores should be evidence-based — supported by demos, references, data, or documented evaluation — not gut feel
- **Weighted Score**: For each option-criterion pair: Score × Weight. The total weighted score across all criteria is the option's overall score
- **Sensitivity Analysis**: Testing whether the ranking changes under different weight assumptions. If Option A wins only when one criterion is weighted heavily, the decision is sensitive to that weight and the weighting assumption should be examined
- **Facilitation Value**: The decision matrix's value is as much in the facilitation process as in the output. When stakeholders assign weights and scores collaboratively, hidden disagreements surface — one person weights security at 30%; another weights it at 5%. Resolving the weighting is the actual decision
- **Pugh Matrix (Concept Scoring)**: A variant where one option is designated as the baseline; others are scored as better (+), same (S), or worse (−) on each criterion. Useful early in evaluation when quantitative scoring is premature
- **Limitations**: Decision matrices can be gamed — criteria and weights can be selected to favor a predetermined option. Transparent facilitation and independent review of weight assignments reduce this risk

## Method Application
Method uses decision matrices for vendor selection, architecture options, and technology investment decisions. The matrix provides the audit trail for recommendations — when a client's procurement team asks "why did you recommend Vendor A over Vendor B?", the weighted scorecard is the answer. Method also uses the matrix process to align stakeholders on evaluation criteria before scoring, which resolves most disagreements before they become post-recommendation conflicts.

## Consulting Insight
🎯 **Consulting Tool — Decision Matrix**: The facilitation moment that produces the most value is having stakeholders assign weights before they see the scores. When weights are assigned after scoring — or after a preferred option is visible — the weights are post-rationalization, not evaluation criteria. Run the weighting session first, get sign-off from key stakeholders, then apply scores. If stakeholders try to revise weights after seeing results, that's not evaluation — it's negotiation. Name it as such. → `consulting-tools-repository/decision-matrix.md`

## Related Entries
- [Iron Triangle](iron-triangle.md) — decision criteria for delivery options should reflect the fixed and flexible triangle vertices
- [Risk Register](risk-register.md) — risk scores for each option can be incorporated as a weighted criterion in the decision matrix
- [MoSCoW Prioritization](moscow-prioritization.md) — within a MoSCoW tier, a decision matrix provides quantitative ranking
- [RICE Scoring](rice-scoring.md) — RICE is a specialized decision matrix optimized for product feature prioritization
- [Build vs. Buy vs. Partner](build-buy-partner.md) — structured decision matrix is the recommended tool for build/buy/partner analysis where the options are close

---
id: pre-mortems
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [blameless-postmortems, rfcs-and-design-docs, chaos-engineering, estimation-and-planning]
complexity: foundational
---

# Pre-Mortems

## What It Is
A structured anticipatory exercise where a team imagines that a project, launch, or change has already failed — then works backward to identify what caused the failure. Unlike risk registers or threat modeling (which ask "what could go wrong?"), a pre-mortem asks "it's six months from now, this project failed spectacularly — why?" The future-failure framing unlocks candid thinking that people suppress in forward-looking planning discussions where optimism bias and social dynamics favor positive framings. Developed by Gary Klein, pre-mortems are a proven technique for surfacing project risks that would otherwise remain unspoken.

## When to Apply
- Before major launches or go-live events
- At project kickoff for high-stakes or high-complexity initiatives
- When a team senses unstated concerns that aren't surfacing in planning discussions
- Before significant architectural decisions with long-term implications
- When stakeholder pressure is creating optimism bias in planning assumptions

## Key Concepts
- **The Inversion**: Standard planning asks "what could go wrong?" — the pre-mortem asks "it has already gone wrong, why?" This small reframe produces dramatically more honest and specific failure modes. People are better at explaining past events than predicting future ones
- **Facilitation Format**:
  1. *Setup*: "Imagine it's 6 months from now. This project has failed — it missed the deadline, the system went down at launch, the client is furious, whatever failure looks worst. We're meeting to debrief on why."
  2. *Individual brainstorm*: Participants silently write down all the reasons it failed (3-5 minutes). Private writing prevents anchoring on the first idea spoken
  3. *Round-robin sharing*: Each person shares one reason. Facilitator captures on a shared board. Continue rounds until ideas are exhausted
  4. *Prioritization*: Group votes on highest-impact failure modes
  5. *Mitigation*: For top failure modes, determine if the team will change the plan, add checkpoints, or accept the risk
- **Psychological Safety**: Pre-mortems work because they give people permission to voice pessimistic views without seeming disloyal. "The project will fail because we don't have enough senior backend capacity" is easier to say when everyone is playing the future-failure game
- **Outputs**: The pre-mortem produces (a) a ranked list of failure modes and (b) specific plan changes or risk mitigations for the top risks. Capture these in the project plan or risk log. A pre-mortem that surfaces risks but produces no plan changes is incomplete
- **Pre-Mortem vs. Post-Mortem**: A post-mortem learns from what already happened; a pre-mortem prevents it. Both practices are blameless — the pre-mortem assumes the failure is hypothetical, which makes it even safer to be candid
- **Frequency**: Run at major milestones, not just project start. A pre-mortem before a phased launch (beta → GA) catches new risks that weren't visible at kickoff
- **Common Failure Modes Surfaced**: Unclear ownership, underestimated scope, dependency on unavailable stakeholders, misaligned assumptions between engineering and product, insufficient testing time, external API risks, data migration risks

## In Practice
Method runs pre-mortems at engagement kickoff and before major go-live events. A 30-minute pre-mortem is included in the project plan template for all client engagements. Outputs feed directly into the project risk log. The highest-impact failure modes are reviewed at each status meeting as an early-warning checklist. Program managers facilitate; all team members (engineering, product, design) participate.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Pre-Mortems**: The pre-mortem surfaces the things your team knows but is reluctant to say in normal planning discussions — unclear ownership, missing expertise, unrealistic timelines, dependencies no one has confirmed. The future-failure frame makes it safe to be honest. A 30-minute pre-mortem at project kickoff is one of the highest-ROI planning activities in software delivery. Capture outputs in the risk log, not just in someone's notes. → `engineering-knowledge-repository/pre-mortems.md`

## Related Entries
- [Blameless Post-Mortems](blameless-postmortems.md) — post-mortems learn from real failures; pre-mortems prevent future ones
- [RFCs and Design Docs](rfcs-and-design-docs.md) — pre-mortem outputs can feed risk sections of design docs
- [Chaos Engineering](chaos-engineering.md) — chaos engineering tests failure modes that pre-mortems help identify
- [Estimation and Planning](estimation-and-planning.md) — pre-mortems surface estimation risks and planning assumptions that should be challenged


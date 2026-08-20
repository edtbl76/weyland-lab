---
id: cynefin
tags: [systems-thinking, organizational, delivery]
surfaces-at: [validated-intent, requirements-analysis, workflow-planning]
related: [wardley-mapping, causal-loop-diagrams, theory-of-constraints, decision-matrix, risk-register]
complexity: advanced
---

# Cynefin Framework

## What It Is
A sense-making framework developed by Dave Snowden at IBM that categorizes problems and situations into five domains based on the relationship between cause and effect: Clear (formerly Simple), Complicated, Complex, Chaotic, and Disorder (the center). Each domain requires a different decision-making approach — best practice in Clear, expert analysis in Complicated, experimentation in Complex, and immediate stabilizing action in Chaotic. Cynefin is not a categorization tool for problems themselves, but for the context in which decisions are being made. The same problem can be in different domains depending on the organization's knowledge and the stability of the environment.

## When to Use
- When a team is applying a complicated solution to a complex problem (the most common failure mode)
- Diagnosing why a prescribed methodology isn't working — it may be mismatched to the problem domain
- Structuring how to approach unknowns at the start of a program: what can be analyzed vs. what must be probed
- Executive alignment: helping leaders understand why some situations require experimentation rather than planning
- Risk discussions: separating known risks (Complicated) from emergent risks (Complex) to apply appropriate responses

## Key Concepts
- **Clear (Simple)**: Cause and effect are obvious. Best practices apply. Sense → Categorize → Respond. Risk: complacency, oversimplification of complex situations into this domain. Examples: standard expense approval, password reset
- **Complicated**: Cause and effect are separated but discoverable through expertise. Good practices (multiple valid approaches) apply. Sense → Analyze → Respond. Domain of experts. Examples: complex engineering system, legal compliance, financial modeling
- **Complex**: Cause and effect are only apparent in retrospect; the situation is unpredictable. Emergent practices apply. Probe → Sense → Respond. Multiple small experiments rather than one big plan. Examples: culture change, product-market fit, new market entry. **Most innovation and transformation work lives here**
- **Chaotic**: No perceivable cause-and-effect relationship. Novel practice. Act → Sense → Respond. The goal is immediate stabilization to move out of chaos. Examples: active crisis, system outage, sudden regulatory change
- **Disorder**: The center — you don't know which domain you're in. The most dangerous state. Default action is to break the situation into parts and address each part in its domain
- **Complexity vs. Complicated**: The most important distinction. Complicated problems are solvable through analysis and expertise. Complex problems are not — they require experimentation, adaptive management, and tolerance for emergence. Treating a complex problem as complicated produces plans that fail
- **Safe-to-Fail Experiments**: In the Complex domain, the appropriate approach is running multiple small experiments designed to succeed or fail safely — not large bets on predicted outcomes
- **Domain Drift**: Situations move between domains. A Clear domain can suddenly become Chaotic (a regulatory change makes the established best practice illegal). Cynefin encourages continuous re-sensing rather than permanent classification

## Method Application
Method uses Cynefin to calibrate delivery approach to problem type. When a client wants a detailed delivery plan for a complex problem, Cynefin provides the language to explain why a plan-heavy approach is mismatched — and why an iterative, probe-and-respond approach is more appropriate. It also reframes risk: in the Complex domain, the risk isn't failing to execute the plan; it's failing to learn quickly enough.

## Consulting Insight
🎯 **Consulting Tool — Cynefin**: The most valuable Cynefin intervention is preventing a client from treating a Complex problem as Complicated. The giveaway is a detailed project plan for an uncertain outcome: a 12-month roadmap to achieve culture change, a fixed-price scope for market entry in an unknown segment, a waterfall delivery plan for a first-generation product. When you see over-specified planning for under-specified problems, introduce Cynefin. The framework gives clients permission to say "we don't know yet" — and structures what to do instead. → `consulting-tools-repository/cynefin.md`

## Related Entries
- [Wardley Mapping](wardley-mapping.md) — Genesis/Custom-Built components on a Wardley Map are in the Complex domain; Commodity components are in Clear or Complicated
- [Causal Loop Diagrams](causal-loop-diagrams.md) — CLD thinking applies to Complex domain problems where feedback loops drive behavior
- [Theory of Constraints](theory-of-constraints.md) — ToC applies in the Complicated domain; problems are solvable through systematic constraint analysis
- [Decision Matrix](decision-matrix.md) — structured decision tools apply in the Complicated domain; in Complex, decisions are made through experiment not analysis
- [Risk Register](risk-register.md) — risk categories should reflect Cynefin domain: known risks (Complicated), emergent risks (Complex), crisis indicators (Chaotic)

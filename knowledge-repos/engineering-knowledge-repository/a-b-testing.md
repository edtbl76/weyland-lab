---
id: a-b-testing
tags: [methodology, ai-ml, backend]
surfaces-at: [application-design, nfr-requirements]
related: [offline-vs-online-evaluation, champion-challenger-testing, shadow-mode-deployment, model-monitoring]
complexity: intermediate
---

# A/B Testing

## What It Is
A controlled experiment that randomly assigns users to two or more variants (A = control, B = treatment) to measure the causal impact of a change on a business metric. In software and ML systems, A/B testing validates that a new feature, model, or algorithm actually improves the business outcome it was designed to improve — as opposed to showing better offline metrics that don't translate to user value. It is the gold standard for measuring causal impact in production systems.

## When to Apply
- Validating that a new ML model improves business metrics before full rollout
- Testing UI, product, or algorithm changes with user-visible effects
- Any decision where directional intuition is insufficient and data-driven causal evidence is needed
- After shadow mode confirms a new model is operationally sound

## Key Concepts
- **Randomization Unit**: The entity randomly assigned to control or treatment — typically user, session, or request. Randomize at the right level to avoid interference between units (network effects require cluster randomization)
- **Statistical Significance and Power**: Pre-compute the required sample size using power analysis — specify the minimum detectable effect (MDE), significance level (α, typically 0.05), and power (1-β, typically 0.80). Running the experiment until results look good is p-hacking
- **Minimum Detectable Effect (MDE)**: The smallest business-meaningful improvement the experiment is designed to detect. Smaller MDEs require larger sample sizes
- **Primary and Guardrail Metrics**: Define one primary metric (what you're optimizing) and guardrail metrics (what you're not allowed to harm — latency, error rate, retention) before starting. Do not add metrics post-hoc
- **Novelty Effect**: Users behave differently with new experiences initially — results may not reflect long-term behavior. Run experiments long enough to see post-novelty-effect stabilization
- **Interaction Effects**: Multiple simultaneous A/B tests can interfere with each other if their randomization units overlap. Use orthogonal experiment design or mutually exclusive traffic splits
- **Shipment Decision**: Stop the experiment only when the pre-specified sample size is reached or a predetermined time limit passes. Do not stop early because results look significant (sequential testing methods like CUPED/SPRT handle early stopping correctly)
- **Feature Flags**: A/B test infrastructure typically uses feature flags to control which variant a user sees — enables clean rollout and instant rollback

## In Practice
Method A/B tests for ML models use champion-challenger traffic splitting. Sample size is pre-computed using power analysis with a defined MDE. Experiments run for a minimum of two weeks to account for novelty effects and weekly seasonality. Primary metric, guardrail metrics, and significance threshold are defined in the experiment plan before launch.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — A/B Testing**: Define your primary metric, guardrail metrics, MDE, and required sample size before launching — running until you see significance is p-hacking. Randomize at the right unit level (user vs. session vs. request) to prevent interference. Run experiments long enough to clear novelty effects — typically two weeks minimum. Never run multiple overlapping experiments on the same traffic without orthogonal design. Ship only when the pre-specified sample size is reached; use sequential testing methods (SPRT) if you need valid early stopping. → `engineering-knowledge-repository/a-b-testing.md`

## Related Entries
- [Offline vs. Online Evaluation](offline-vs-online-evaluation.md) — A/B testing is the primary online evaluation method
- [Champion-Challenger Testing](champion-challenger-testing.md) — ML-specific variant of A/B testing for model comparison
- [Shadow Mode Deployment](shadow-mode-deployment.md) — operational validation before A/B test traffic exposure
- [Model Monitoring](model-monitoring.md) — monitor experiment variants for operational health during the test

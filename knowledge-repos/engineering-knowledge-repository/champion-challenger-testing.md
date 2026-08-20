---
id: champion-challenger-testing
tags: [pattern, ai-ml, deployment, backend]
surfaces-at: [application-design, infrastructure-design]
related: [model-serving, offline-vs-online-evaluation, shadow-mode-deployment, canary-deployment, model-registry]
complexity: intermediate
---

# Champion/Challenger Testing

## What It Is
A production deployment pattern where a new model (the challenger) serves a small percentage of real traffic alongside the current production model (the champion), allowing direct comparison on real-world data before full promotion. The champion continues serving the majority of traffic while the challenger accumulates enough predictions and outcomes to make a statistically valid comparison. If the challenger wins, it becomes the new champion; if not, it is rolled back.

## When to Apply
- Deploying a retrained model to production when offline evaluation is insufficient to confirm improvement
- High-stakes models (ranking, recommendations, pricing) where production behavior may differ from offline metrics
- When you need to validate that a model improvement in offline metrics translates to business metric improvement

## When Not to Apply
- When the user experience impact of serving different predictions to different users is unacceptable
- Real-time safety-critical systems where any degradation during the test period is unacceptable
- When you have insufficient traffic to reach statistical significance in a reasonable time window

## Key Concepts
- **Traffic Split**: The challenger receives a small percentage of traffic (5-10%) — enough to accumulate signal while limiting exposure. The split can be increased as confidence grows
- **Consistent User Assignment**: Users should be consistently assigned to champion or challenger — avoid showing the same user different recommendations. Hash user ID to determine assignment
- **Metric Definition**: Define success metrics before the test — primary metric (the one that determines winner), guardrail metrics (must not degrade). Example: primary = CTR, guardrail = latency P99, engagement rate
- **Statistical Significance**: Accumulate enough predictions and outcomes to detect the expected effect size with sufficient power. Underpowered tests produce false conclusions. Use a power calculator before starting
- **Minimum Detectable Effect (MDE)**: The smallest improvement worth detecting. Determines required sample size. Don't run a test if you can't detect the MDE in a reasonable time window
- **Sequential Testing**: Traditional A/B tests require a fixed sample size before peeking. Sequential testing (e.g., mSPRT) allows early stopping when a result is clear, reducing test duration
- **Infrastructure**: Model serving infrastructure must support traffic splitting — KServe, Seldon, and Istio's traffic management handle weighted routing across model versions
- **Logging**: Every prediction must log the model version that served it alongside the outcome when it arrives. This is the data that determines the winner

## In Practice
Method champion/challenger tests run at 90/10 splits using KServe traffic management. User assignment is hash-based for consistency. Primary and guardrail metrics are defined in the test plan before deployment. Results are reviewed after reaching the pre-calculated sample size — not peeked at before. Winning challengers are promoted via model registry stage transition and a full traffic shift.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Champion/Challenger Testing**: Offline metrics lie — production validates. Run the challenger at 5-10% traffic alongside the champion. Define success metrics and guardrail metrics before the test — never define them after seeing results. Wait for statistical significance (use a power calculator to determine sample size upfront). Hash users to model version for consistent assignments. Log the serving model version with every prediction so you can attribute outcomes correctly. Traffic splitting requires infrastructure support — KServe, Istio weighted routing. → `engineering-knowledge-repository/champion-challenger-testing.md`

## Related Entries
- [Model Serving](model-serving.md) — traffic splitting is implemented in the serving layer
- [Offline vs. Online Evaluation](offline-vs-online-evaluation.md) — champion/challenger is the gold-standard online evaluation
- [Shadow Mode Deployment](shadow-mode-deployment.md) — shadow mode is the safer precursor to champion/challenger
- [Canary Deployment](canary-deployment.md) — the same traffic-splitting pattern applied to software; model champion/challenger is the ML equivalent
- [Model Registry](model-registry.md) — champion promotion is a model registry stage transition

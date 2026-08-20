---
id: shadow-mode-deployment
tags: [pattern, ai-ml, deployment, reliability, backend]
surfaces-at: [application-design, infrastructure-design]
related: [champion-challenger-testing, model-serving, model-monitoring, canary-deployment, offline-vs-online-evaluation]
complexity: intermediate
---

# Shadow Mode Deployment

## What It Is
A deployment pattern where a new model runs in production alongside the current model, receiving the same inputs and producing predictions, but whose outputs are not served to users. The shadow model's predictions are logged and compared against the champion model's predictions (and eventually against ground truth outcomes) — validating behavior on real production traffic before the model has any user-facing impact. The safest way to validate a new model in production.

## When to Apply
- Before champion/challenger testing — shadow mode is the lower-risk precursor
- When validating a new model on production data that significantly differs from the training distribution
- For high-stakes models where any degradation in champion/challenger would be unacceptable
- When testing infrastructure changes (new serving framework, hardware) alongside model changes

## When Not to Apply
- When shadow mode infrastructure cost is prohibitive (running two models in parallel)
- Simple low-risk model updates where offline evaluation is sufficient

## Key Concepts
- **Dual Serving**: The prediction request is sent to both the champion and the shadow model. Only the champion's response is returned to the user; the shadow response is discarded (or logged)
- **Prediction Logging**: Every shadow prediction is logged alongside the champion prediction and the request features. This creates a dataset for comparison
- **Prediction Divergence Analysis**: Compare shadow vs. champion predictions — where do they disagree? Disagreements highlight cases where the new model behaves differently and warrant investigation
- **Outcome Correlation**: When ground truth labels arrive, compare accuracy of shadow vs. champion on production data. This is the pre-flight check before champion/challenger
- **Latency Impact**: Running two models doubles inference compute. The shadow model can run asynchronously after the champion response is returned — eliminates latency impact but requires async architecture
- **Async Shadow Pattern**: Return the champion's response immediately; fire-and-forget the shadow model call asynchronously for logging only. Eliminates latency overhead while preserving all validation value
- **Infrastructure Similarity**: Shadow mode also validates infrastructure — does the new serving environment handle production traffic patterns? Discovers operational issues before they affect users

## In Practice
Method high-stakes model deployments follow: shadow mode (1-2 weeks, validate divergence) → champion/challenger (validate business metrics) → full promotion. Shadow runs asynchronously to avoid latency impact. Divergence reports are reviewed daily by the ML team. Shadow mode is also used when migrating serving infrastructure (e.g., moving from CPU to GPU serving) independently of model changes.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Shadow Mode Deployment**: Zero user impact, real production validation. Run the new model on production traffic; log its predictions; don't show them to users. Analyze prediction divergence against the champion — high divergence is a flag for investigation. Run async shadow to avoid adding latency. After 1-2 weeks of shadow data with acceptable divergence and outcome correlation, graduate to champion/challenger. Use shadow mode to validate infrastructure changes independently of model changes. The safer the model, the more expensive the failure — use shadow mode. → `engineering-knowledge-repository/shadow-mode-deployment.md`

## Related Entries
- [Champion/Challenger Testing](champion-challenger-testing.md) — shadow mode is the precursor; champion/challenger follows successful shadow validation
- [Model Serving](model-serving.md) — dual serving infrastructure required for shadow mode
- [Model Monitoring](model-monitoring.md) — shadow prediction logs feed monitoring and divergence analysis
- [Canary Deployment](canary-deployment.md) — shadow mode for software is analogous to canary; both limit production exposure
- [Offline vs. Online Evaluation](offline-vs-online-evaluation.md) — shadow mode bridges offline evaluation and live champion/challenger

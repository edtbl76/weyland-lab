---
id: offline-vs-online-evaluation
tags: [methodology, ai-ml, backend]
surfaces-at: [application-design, nfr-requirements]
related: [model-evaluation-metrics, llm-evaluation, champion-challenger-testing, shadow-mode-deployment, a-b-testing, model-monitoring]
complexity: intermediate
---

# Offline vs. Online Evaluation

## What It Is
Two complementary evaluation paradigms for ML systems. **Offline evaluation** assesses model performance using historical data before deployment — fast, cheap, and reproducible but may not predict production behavior. **Online evaluation** assesses model impact on real users in production — the ground truth for business value but slow, expensive, and only possible post-deployment. The gap between offline and online performance is one of the central challenges in applied ML.

## When to Apply
- Offline evaluation: always, as a deployment gate before any model reaches production
- Online evaluation: A/B test or champion-challenger test for any model change with significant business impact
- Both: the standard practice — offline validates correctness, online validates business value

## Key Concepts

**Offline Evaluation**:
- Evaluation on a static held-out dataset using historical labels
- Fast feedback loop — hours or days vs. weeks for online
- Reproducible — same dataset, same results
- Limitations: distribution shift between test data and production, feedback loop gaps (labels from production behavior not in training data), proxy metrics may not correlate with business metrics

**Online Evaluation**:
- A/B testing: random assignment of users to control (current model) and treatment (new model) — measures causal impact on business metrics
- Champion-challenger testing: route a percentage of traffic to the challenger model, compare live performance metrics
- Shadow mode: new model runs in parallel, predictions logged but not served — validate without user impact
- Requires sufficient traffic volume for statistical significance

**The Offline-Online Gap**:
- Common causes: covariate shift (production data distribution differs from test set), feedback loops (model predictions affect future labels), missing features at serving time, latency constraints affecting what features are computable
- Mitigation: use production data distribution in test sets when possible, temporal splits for time-sensitive tasks, shadow mode before full deployment

**Metric Alignment**:
- Offline metrics (AUC, F1) are proxies — they must be shown to correlate with online business metrics (revenue, click-through rate, retention)
- Validate the offline-online correlation historically before trusting offline metrics as deployment gates

**Statistical Significance**:
- Online experiments require sufficient sample size to detect meaningful effect sizes
- Pre-compute required sample size (power analysis) before launching A/B tests
- Set significance threshold and minimum detectable effect before seeing results — avoid p-hacking

## In Practice
Method ML deployments always include both stages: offline evaluation (held-out test set + CV) as a deployment gate, then shadow mode or champion-challenger for online validation. A/B tests are used for high-impact model changes. Statistical significance and minimum detectable effect are defined before launching online experiments.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Offline vs. Online Evaluation**: Offline metrics are necessary but not sufficient — a model with great AUC can fail to move business metrics online. Always validate offline-online metric correlation before trusting your eval suite. Use shadow mode to safely compare new models without user impact before routing live traffic. For significant model changes, A/B test with pre-computed sample sizes and significance thresholds — don't eyeball results. The offline-online gap is real; close it by using production-distribution test sets and temporal train/test splits. → `engineering-knowledge-repository/offline-vs-online-evaluation.md`

## Related Entries
- [Model Evaluation Metrics](model-evaluation-metrics.md) — metrics used in offline evaluation
- [LLM Evaluation](llm-evaluation.md) — LLM-specific evaluation including both offline and online approaches
- [Champion-Challenger Testing](champion-challenger-testing.md) — production strategy for online model comparison
- [Shadow Mode Deployment](shadow-mode-deployment.md) — run a new model in production without serving its predictions
- [A/B Testing](a-b-testing.md) — controlled online experiment for measuring causal model impact
- [Model Monitoring](model-monitoring.md) — ongoing online performance tracking after deployment

---
id: data-drift
tags: [pattern, ai-ml, data, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [model-monitoring, concept-drift, training-serving-skew, continuous-training, feature-stores]
complexity: intermediate
---

# Data Drift

## What It Is
A change in the statistical distribution of input features between when a model was trained and when it is serving predictions in production. Data drift causes model performance to degrade because the model is being asked to make predictions on data that looks different from what it learned from. It is one of the two primary forms of distribution shift (the other being concept drift) and is detectable without ground truth labels.

## When to Apply
- Monitoring all production ML models — data drift detection should be a default operational concern
- During model debugging when unexplained performance degradation is observed
- As part of CT pipeline triggers

## Key Concepts
- **Covariate Shift**: The technical term for data drift — the marginal distribution of inputs P(X) changes while the conditional distribution P(Y|X) remains stable. The model's learned relationship is still valid; it's just being applied to out-of-distribution inputs
- **Feature Drift vs. Dataset Drift**: Feature drift occurs in one or a few features. Dataset drift is a widespread shift across many features simultaneously — often indicates an upstream data pipeline change or a fundamental change in user behavior
- **Statistical Tests for Drift**:
  - *Kolmogorov-Smirnov (KS) test*: Non-parametric test comparing two distributions. Works for continuous features
  - *Chi-squared test*: For categorical features — compares observed vs. expected frequency distributions
  - *Population Stability Index (PSI)*: PSI < 0.1 = no significant change; 0.1–0.2 = moderate change; > 0.2 = significant drift. Widely used in financial ML
  - *Jensen-Shannon Divergence*: Symmetric measure of distribution similarity. Bounded [0,1]; 0 = identical distributions
- **Reference Window**: The baseline distribution to compare against — typically the training dataset or a stable recent production window. The reference is fixed; current data is compared against it periodically
- **Drift Severity**: Not all drift is actionable. Drift in a high-importance feature with high severity warrants retraining. Drift in a low-importance feature with low severity may not affect model performance
- **Embedding Drift**: For NLP and LLM applications, drift in the embedding space — queries/documents are moving toward a different region of the semantic space. Requires dimensionality reduction visualization (UMAP, t-SNE) to detect and interpret
- **Upstream Cause Investigation**: Data drift is often a symptom of upstream changes — a data pipeline bug, a product change affecting user behavior, or a seasonal pattern. Identify the root cause before retraining

## In Practice
Method production ML systems run daily PSI calculations on all input features against the training distribution. Features with PSI > 0.1 are flagged for review. PSI > 0.2 triggers an alert to the ML team. Consecutive alerts trigger the CT pipeline. Root cause investigation is part of the drift response process — drift from a pipeline bug should fix the bug, not retrain on corrupted data.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Drift**: Drift is inputs changing, not the model's learned rules. Detect it with PSI (quick, interpretable) or KS test (statistically rigorous). Compare against a stable reference window from training. PSI > 0.2 is a conventional alert threshold — validate empirically. Investigate the upstream cause before retraining — drift from a pipeline bug poisons the new training data too. Distinguish data drift (P(X) changes) from concept drift (P(Y|X) changes) — they require different responses. → `engineering-knowledge-repository/data-drift.md`

## Related Entries
- [Model Monitoring](model-monitoring.md) — data drift is one of the three monitoring layers
- [Concept Drift](concept-drift.md) — the companion form of distribution shift affecting the target relationship
- [Training-Serving Skew](training-serving-skew.md) — a related but distinct cause of input distribution mismatch
- [Continuous Training](continuous-training.md) — drift detection triggers CT when drift exceeds thresholds
- [Feature Stores](feature-stores.md) — feature stores track feature distributions over time, enabling drift detection

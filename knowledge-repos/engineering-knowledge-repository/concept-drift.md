---
id: concept-drift
tags: [pattern, ai-ml, data, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [model-monitoring, data-drift, continuous-training, model-evaluation-metrics, human-in-the-loop]
complexity: intermediate
---

# Concept Drift

## What It Is
A change in the underlying relationship between input features and the target variable — P(Y|X) changes over time. Unlike data drift (where the inputs change but the relationship is stable), concept drift means the model's learned rules are becoming incorrect. A fraud detection model trained when fraudsters used pattern A will degrade when fraudsters adapt to pattern B — the inputs may look similar, but what constitutes fraud has changed. Concept drift requires retraining to correct.

## When to Apply
- Monitoring models in adversarial environments (fraud, spam, abuse) — attackers adapt continuously
- Any model where ground truth labels can be collected with a reasonable lag
- Long-running models (>3 months) where the world has likely evolved

## Key Concepts
- **Sudden Drift**: An abrupt change in the relationship — a policy change, a crisis, a competitor action. Performance drops sharply
- **Gradual Drift**: A slow, continuous shift — user preferences evolving, language changing, market dynamics shifting. Performance erodes slowly over time
- **Recurring Drift**: Seasonal patterns — a model trained on non-holiday data degrades during holidays; performance recovers after. Segment-specific models or seasonal retraining addresses this
- **Detecting Concept Drift**: Requires ground truth labels — you can't see concept drift in the inputs alone. Methods:
  - Monitor predictive performance metrics (accuracy, AUC-ROC, precision/recall) on labeled production samples
  - Monitor business proxy metrics (CTR, conversion) that correlate with prediction quality
  - CUSUM (cumulative sum control chart) or ADWIN (adaptive windowing) for statistical detection of performance change points
- **Label Lag**: Ground truth often arrives late (fraud confirmed days later, click outcomes minutes later). Concept drift monitoring must account for label lag in calculating performance metrics
- **Adversarial Concept Drift**: Deliberate drift — bad actors adapting to evade detection. Requires more frequent retraining and adversarial training data augmentation
- **Drift vs. Model Degradation**: Concept drift means the world changed. Model degradation could also be caused by a data pipeline bug, a feature schema change, or serving skew. Distinguish before retraining
- **Windowed Retraining**: Use a sliding training window (most recent N months) to ensure the model learns current patterns, not outdated historical relationships

## In Practice
Method fraud and recommendation models monitor concept drift via sampled ground truth labels ingested with a 48-hour lag. Performance metrics are tracked on rolling 7-day windows. ADWIN is used for statistical change point detection. Adversarial models retrain weekly regardless of drift signals — the adversarial environment guarantees continuous drift.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Concept Drift**: The world changed, not your code. Concept drift means P(Y|X) shifted — the model's learned rules are stale. You need ground truth labels to detect it — monitor performance metrics on sampled production data with label lag accounted for. Distinguish from data drift (input change) and skew (pipeline bug). Adversarial environments drift constantly — retrain frequently. Use windowed training data (recent N months) so the model learns current patterns. When performance drops, validate it's drift before retraining on potentially corrupted data. → `engineering-knowledge-repository/concept-drift.md`

## Related Entries
- [Model Monitoring](model-monitoring.md) — concept drift is detected through model performance monitoring
- [Data Drift](data-drift.md) — the companion distribution shift in input features (detectable without labels)
- [Continuous Training](continuous-training.md) — concept drift triggers retraining
- [Model Evaluation Metrics](model-evaluation-metrics.md) — performance metrics used to detect concept drift
- [Human-in-the-Loop](human-in-the-loop.md) — human labeling provides the ground truth needed for concept drift detection

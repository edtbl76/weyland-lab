---
id: model-evaluation-metrics
tags: [methodology, ai-ml, backend]
surfaces-at: [application-design, nfr-requirements]
related: [class-imbalance, cross-validation, offline-vs-online-evaluation, llm-evaluation, model-monitoring, experiment-tracking]
complexity: intermediate
---

# Model Evaluation Metrics

## What It Is
Quantitative measures used to assess machine learning model performance. Choosing the right metric is as important as choosing the right model — optimizing for the wrong metric produces models that perform well on paper but fail in production. Metrics must align with business objectives: a fraud detection model optimizing accuracy ignores the rare but costly fraud cases; a churn model optimizing AUC may hide terrible precision at the operating threshold.

## When to Apply
- Selecting a primary optimization metric before model training begins
- Comparing candidate models during experimentation
- Setting performance thresholds for production deployment gates
- Monitoring model health in production

## Key Concepts

**Classification Metrics**:
- **Accuracy**: Fraction of correct predictions. Misleading for imbalanced classes — not useful as primary metric when classes are unequal
- **Precision**: Of predicted positives, fraction that are true positives. Optimize when false positives are costly (spam filter — don't block real email)
- **Recall (Sensitivity)**: Of actual positives, fraction correctly predicted. Optimize when false negatives are costly (cancer detection — don't miss disease)
- **F1 Score**: Harmonic mean of precision and recall. Balances both. Standard for imbalanced classification
- **AUC-ROC**: Area under the receiver operating characteristic curve. Measures discrimination ability across all thresholds. Higher is better; 0.5 = random. Useful aggregate but can be misleading when class imbalance is severe
- **AUC-PR (Average Precision)**: Area under the precision-recall curve. More informative than AUC-ROC for imbalanced problems — focuses on the minority class
- **Matthews Correlation Coefficient (MCC)**: Single metric that accounts for all four confusion matrix cells. Robust to class imbalance. Range: -1 to +1; +1 is perfect

**Regression Metrics**:
- **MAE (Mean Absolute Error)**: Average absolute difference between predicted and actual. Interpretable in original units; robust to outliers
- **RMSE (Root Mean Squared Error)**: Penalizes large errors more than MAE. Use when large errors are disproportionately costly
- **R² (Coefficient of Determination)**: Fraction of variance explained. Interpretable as a percentage; useful for comparing across datasets

**Ranking/Retrieval Metrics**:
- **NDCG (Normalized Discounted Cumulative Gain)**: Measures ranking quality, weighting higher-ranked relevant results more. Standard for search and recommendation
- **MRR (Mean Reciprocal Rank)**: Average of the reciprocal of the rank of the first relevant result. Simple ranking metric

**LLM/Generation Metrics**:
- **BLEU, ROUGE**: N-gram overlap metrics for machine translation and summarization. Crude proxies — correlate poorly with human judgment
- **BERTScore**: Semantic similarity using BERT embeddings — better than n-gram metrics
- **LLM-as-Judge**: Use a strong LLM to evaluate outputs on rubric criteria. Current best practice for open-ended generation quality

**Alignment Between Metric and Business Goal**:
- Define the business cost of false positives vs. false negatives before choosing a metric
- Set the operating threshold *after* training based on business constraints — don't accept the 0.5 default

## In Practice
Method ML projects define the primary business metric and optimization metric before any modeling. Classification tasks default to AUC-PR + F1 at the operating threshold. Regression uses RMSE + MAE together. LLM tasks use LLM-as-Judge for quality plus task-specific metrics. All metrics are logged in MLflow per experiment run.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Model Evaluation Metrics**: Pick the metric that matches the business cost of errors before training — precision when false positives are expensive, recall when false negatives are expensive, AUC-PR for imbalanced problems. Accuracy is useless for imbalanced classification. For LLMs, BLEU and ROUGE are weak proxies — use LLM-as-Judge for quality assessment. Define the classification threshold based on business constraints, not the 0.5 default. Log all metrics per experiment run — multiple metrics together tell a more complete story than one number alone. → `engineering-knowledge-repository/model-evaluation-metrics.md`

## Related Entries
- [Class Imbalance](class-imbalance.md) — imbalanced datasets require precision/recall/F1/AUC-PR instead of accuracy
- [Cross-Validation](cross-validation.md) — CV produces the metric estimates used for model comparison
- [Offline vs. Online Evaluation](offline-vs-online-evaluation.md) — offline metrics must be validated against online business metrics
- [LLM Evaluation](llm-evaluation.md) — LLM-specific evaluation metrics and frameworks
- [Model Monitoring](model-monitoring.md) — production monitoring tracks model metrics over time
- [Experiment Tracking](experiment-tracking.md) — all metric values are logged per experiment run

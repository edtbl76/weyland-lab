---
id: continuous-training
tags: [methodology, ai-ml, deployment, backend]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [mlops, data-drift, concept-drift, model-monitoring, ml-pipelines, model-registry, feature-stores]
complexity: intermediate
---

# Continuous Training

## What It Is
The automated retraining and redeployment of ML models in response to triggers — data drift, performance degradation, scheduled intervals, or new labeled data availability. Analogous to CI/CD for software but applied to model training pipelines. Continuous training (CT) ensures models remain accurate as the world changes without requiring manual intervention for each retraining cycle.

## When to Apply
- Models deployed on data distributions that change over time (user behavior, language, market data)
- When manual retraining cycles are too slow for the business requirement
- When model monitoring detects drift beyond an acceptable threshold

## When Not to Apply
- Static prediction tasks where the data distribution is stable — scheduled retraining is sufficient
- When retraining cost (compute, data labeling) exceeds the value of freshness
- Early-stage systems where the training pipeline isn't mature enough to automate safely

## Key Concepts
- **Retraining Triggers**:
  - *Schedule*: Weekly/monthly retraining regardless of performance. Simple; may retrain unnecessarily
  - *Data trigger*: New labeled data exceeds a threshold (e.g., 10k new examples). Natural for high-throughput labeling pipelines
  - *Drift trigger*: Automated monitoring detects data or concept drift beyond a threshold. Most efficient; requires mature monitoring
  - *Performance trigger*: Online metrics (CTR, conversion, accuracy on sampled data) drop below SLO. Directly tied to business impact
- **Automated Pipeline**: CT requires the training pipeline to be fully automated — no manual steps, notebook dependencies, or human data manipulation. The pipeline must be idempotent and reproducible
- **Validation Gate**: Newly trained models must pass automated evaluation before deployment. If the new model underperforms the current production model, deployment is blocked and an alert fires
- **Champion/Challenger**: A safe CT pattern — new model (challenger) serves a small traffic slice alongside the current (champion) before full promotion. Validates on real traffic before full rollout
- **Cold Start Risk**: Automated CT can deploy a degraded model faster than humans notice — automated rollback (when online metrics drop) is the critical safety mechanism
- **Data Freshness vs. Quality**: More recent data isn't always better training data — it may be noisier, sparser, or reflect a temporary anomaly. CT pipelines should include data quality checks before training
- **Continuous Training vs. Online Learning**: CT retrains a batch model periodically. Online learning updates model weights incrementally on each new example. Online learning is more complex and riskier; CT is the standard approach for most use cases

## In Practice
Method ML systems use scheduled CT (weekly) as the baseline, with drift-triggered CT added for systems where weekly retraining is insufficient. Kubeflow Pipelines or Airflow orchestrates the automated pipeline. All CT runs go through the model registry with automated evaluation gating. Automated rollback reverts to the previous production model if online metrics degrade within 24 hours of deployment.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Continuous Training**: Models degrade as data changes — automate retraining before it becomes a crisis. Start with scheduled CT (weekly); add drift triggers when you have mature monitoring. The entire training pipeline must be automated and idempotent — no manual steps. Always gate deployment: new model must outperform current production model on the evaluation set. Use champion/challenger for high-stakes models. Automated rollback is mandatory — CT can deploy a bad model faster than humans catch it. → `engineering-knowledge-repository/continuous-training.md`

## Related Entries
- [MLOps](mlops.md) — continuous training is the CT in MLOps CT/CD
- [Data Drift](data-drift.md) — drift detection is a primary CT trigger
- [Concept Drift](concept-drift.md) — concept drift signals that retraining is needed
- [Model Monitoring](model-monitoring.md) — monitoring provides the performance triggers for CT
- [ML Pipelines](ml-pipelines.md) — CT runs are executed as automated ML pipelines
- [Model Registry](model-registry.md) — CT outputs are registered and gated before deployment
- [Feature Stores](feature-stores.md) — CT pipelines pull fresh features from the feature store

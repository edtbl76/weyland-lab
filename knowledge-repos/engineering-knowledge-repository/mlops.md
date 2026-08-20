---
id: mlops
tags: [methodology, ai-ml, deployment, backend]
surfaces-at: [nfr-requirements, infrastructure-design, requirements-analysis]
related: [continuous-training, model-registry, experiment-tracking, feature-stores, model-monitoring, ml-pipelines, site-reliability-engineering]
complexity: intermediate
---

# MLOps

## What It Is
The practice of applying DevOps principles — automation, versioning, monitoring, and continuous improvement — to machine learning systems. MLOps addresses the unique operational challenges of ML: models degrade over time as data distributions shift, training pipelines are complex multi-step processes, and reproducing a model requires versioning code, data, and hyperparameters together. The goal is to move ML systems from experimental notebooks to reliable, maintainable production systems.

## When to Apply
- Any ML system moving from prototype to production
- Teams that have experienced silent model degradation in production
- When the same data science team is spending more time maintaining models than building new ones

## Key Concepts
- **The Three Axes of ML Versioning**: Code (Git), Data (DVC, Delta Lake), Models (MLflow, W&B). All three must be versioned and linked together to reproduce any model
- **Continuous Training (CT)**: Automatically trigger model retraining based on data drift, schedule, or performance degradation — analogous to CI/CD but for model training pipelines
- **Training Pipeline vs. Serving Pipeline**: Training pipeline: data ingestion → feature engineering → training → evaluation → registration. Serving pipeline: feature retrieval → inference → monitoring. Both must be version-controlled and automated
- **Model Registry**: The central catalog of trained models — versioning, metadata, stage promotion (Staging → Production). Analogous to an artifact registry for ML models
- **Feature Store**: A centralized repository of computed features shared across training and serving — eliminates training-serving skew and enables feature reuse across teams
- **Training-Serving Skew**: The divergence between features available at training time vs. serving time — a primary cause of production model degradation. Feature stores eliminate skew
- **Data Validation**: Automated checks on incoming training data — schema validation, distribution checks, anomaly detection. Catch bad data before it trains a bad model
- **Model Monitoring**: Tracking model performance in production — data drift, concept drift, prediction quality, business metric correlation. Triggers retraining when degradation is detected
- **Mature MLOps Levels** (Google's framework):
  - *Level 0*: Manual, notebook-based training; model deployed manually
  - *Level 1*: Automated training pipeline; manual deployment trigger
  - *Level 2*: Full CT/CD — automated training, evaluation, and deployment on data trigger
- **MLflow**: Open-source platform for experiment tracking, model registry, and pipeline management. The most widely adopted MLOps platform
- **Kubeflow / Vertex AI / SageMaker Pipelines**: Managed MLOps platforms for running pipelines at scale

## In Practice
Method ML engagements target MLOps Level 1 as the production baseline — automated training pipeline triggered manually or on schedule, model registry for versioning, and monitoring for drift. Level 2 (fully automated CT) is introduced when model freshness requirements justify the investment. MLflow is the default experiment tracking and registry tool.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — MLOps**: ML in production requires the same rigor as software — version everything (code, data, model), automate everything (training, evaluation, deployment), monitor everything (data drift, model performance). Start at Level 1: automated training pipeline + model registry + drift monitoring. Add fully automated continuous training (Level 2) when the business requires model freshness within hours. Training-serving skew is the most common silent killer — a feature store prevents it. MLflow is a good default for tracking and registry. → `engineering-knowledge-repository/mlops.md`

## Related Entries
- [Continuous Training](continuous-training.md) — automated retraining pipelines are the CT in MLOps CT/CD
- [Model Registry](model-registry.md) — the model versioning and promotion system
- [Experiment Tracking](experiment-tracking.md) — logging and comparing training runs
- [Feature Stores](feature-stores.md) — shared feature infrastructure that prevents training-serving skew
- [Model Monitoring](model-monitoring.md) — detecting model degradation in production
- [ML Pipelines](ml-pipelines.md) — the orchestration layer for training and serving workflows
- [Site Reliability Engineering](site-reliability-engineering.md) — SRE principles applied to ML systems

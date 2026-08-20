---
id: model-registry
tags: [tooling, ai-ml, deployment, backend]
surfaces-at: [infrastructure-design, application-design]
related: [mlops, experiment-tracking, continuous-training, model-serving, model-monitoring]
complexity: intermediate
---

# Model Registry

## What It Is
A centralized catalog that stores, versions, and manages the lifecycle of trained ML models. The model registry is the handoff point between training (data science) and serving (engineering) — a trained model is registered, validated, and promoted through stages (Staging → Production) before serving real traffic. It provides: versioned model artifacts, metadata (training metrics, data lineage, owner), stage management, and deployment history.

## When to Apply
- Any ML system with more than one model or more than one person deploying models
- Before deploying the first model to production — the registry enables rollback and audit
- When multiple environments (staging, production) need to serve consistent model versions

## Key Concepts
- **Model Version**: Each registered model has an incrementing version number. A version captures the artifact (weights, serialized model), metrics, parameters, training run link, and tags
- **Stage Lifecycle**: Models move through stages — `None` (newly registered), `Staging` (validated, ready for testing), `Production` (serving live traffic), `Archived` (retired). Stage transitions are gated by validation criteria
- **Model Artifact**: The serialized model — `.pkl`, `.pt`, `.onnx`, `.joblib`. Stored alongside metadata in the registry. The registry handles storage; the artifact itself may live in S3 or similar
- **MLflow Model Registry**: The standard OSS model registry — integrated with MLflow experiment tracking. Stage transitions, model annotations, and webhook support for CI/CD triggers
- **Hugging Face Hub**: For transformer and LLM models — the de facto registry for pre-trained models with versioning and access control
- **Model Card**: Documentation accompanying a registered model — intended use, evaluation metrics, training data, limitations, ethical considerations. Best practice for any model serving external users
- **Deployment Trigger**: Stage transition to Production can trigger automated deployment — the CI/CD pipeline monitors the registry for new Production models and deploys automatically
- **Rollback**: When a production model degrades, roll back by promoting the previous Production version. The registry maintains all versions — rollback is a stage transition, not a redeploy
- **Access Control**: Restrict who can promote models to Production — require approval from ML lead or automated evaluation gate

## In Practice
Method ML projects register all models in MLflow. Promotion to Production requires: passing evaluation against the golden test set, ML lead approval, and a staging period with shadow mode comparison against the current production model. Automated webhooks trigger deployment pipelines on Production stage transitions. All production models have model cards.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Model Registry**: The registry is the contract between training and serving. Never deploy a model that isn't registered — you lose versioning, rollback capability, and audit trail. Gate Production promotion: automated evaluation must pass, a human must approve. Rollback is a stage transition — the previous version is always there. Attach model cards to every production model. Use MLflow Registry for custom models; Hugging Face Hub for foundation models. Webhook-triggered deployment on Production promotion closes the CT/CD loop. → `engineering-knowledge-repository/model-registry.md`

## Related Entries
- [MLOps](mlops.md) — the model registry is a core MLOps component
- [Experiment Tracking](experiment-tracking.md) — registered models link back to the training run that produced them
- [Continuous Training](continuous-training.md) — newly trained models are automatically registered after evaluation
- [Model Serving](model-serving.md) — the serving layer pulls artifacts from the model registry
- [Model Monitoring](model-monitoring.md) — production model version is tracked for monitoring and rollback decisions

---
id: experiment-tracking
tags: [tooling, ai-ml, methodology, backend]
surfaces-at: [application-design, code-generation]
related: [mlops, model-registry, hyperparameter-tuning, data-versioning, cross-validation]
complexity: foundational
---

# Experiment Tracking

## What It Is
The systematic recording of ML training runs — hyperparameters, metrics, artifacts, and environment — so experiments are reproducible, comparable, and auditable. Without experiment tracking, teams lose track of which configuration produced the best model, cannot reproduce past results, and repeat work unnecessarily. Experiment tracking is the lab notebook of ML development.

## When to Apply
- Every ML training run beyond the initial exploration — start tracking before you have more than 3 experiments
- Any team where more than one person trains models — shared tracking is essential for collaboration

## Key Concepts
- **Run**: A single training execution with a specific configuration. Each run records: hyperparameters (learning rate, batch size, model architecture), metrics (train/val loss, accuracy, AUC-ROC at each epoch), artifacts (model weights, plots, confusion matrix), and environment (library versions, hardware)
- **Experiment**: A named group of related runs — e.g., "BERT fine-tuning for sentiment classification". Runs within an experiment are compared to find the best configuration
- **MLflow Tracking**: The dominant open-source experiment tracking tool. `mlflow.log_param()`, `mlflow.log_metric()`, `mlflow.log_artifact()`. Provides a UI for run comparison and a REST API for programmatic access
- **Weights & Biases (W&B)**: Managed experiment tracking platform — richer visualization, team collaboration, automated sweeps. Better UX than MLflow; SaaS with data leaving your environment
- **Auto-logging**: MLflow and W&B support auto-logging for common frameworks (scikit-learn, PyTorch, TensorFlow) — automatically captures standard metrics and parameters without explicit logging calls
- **Metric Versioning**: Log metrics at each training step, not just at the end — enables early stopping analysis and training curve comparison between runs
- **Reproducibility Requirements**: To reproduce a run: same code (Git SHA), same data (data version), same hyperparameters (logged), same environment (Docker image or `requirements.txt`). All four must be captured
- **Hyperparameter Sweeps**: Automated search over hyperparameter spaces — grid search, random search, Bayesian optimization. W&B Sweeps and Optuna integrate with experiment tracking to log all sweep trials automatically

## In Practice
Method ML projects use MLflow for experiment tracking. MLflow runs are linked to Git commits and DVC data versions. All hyperparameters are logged at run start; metrics are logged at each epoch. Model artifacts are logged at the best validation metric checkpoint. Experiment names follow a convention: `{project}-{model-family}-{task}`.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Experiment Tracking**: Log everything from the first training run — you will want to reproduce it. Capture: hyperparameters, metrics at each step, model artifacts, Git SHA, data version, library versions. MLflow is the open-source default. W&B is better for teams and visualization but is SaaS. Link runs to code (Git commit) and data (DVC hash) — the three together enable full reproducibility. Use auto-logging where available; add explicit logging for custom metrics. Never compare models without looking at the full training curve, not just the final metric. → `engineering-knowledge-repository/experiment-tracking.md`

## Related Entries
- [MLOps](mlops.md) — experiment tracking is a foundational MLOps practice
- [Model Registry](model-registry.md) — the best run from experiment tracking is promoted to the model registry
- [Hyperparameter Tuning](hyperparameter-tuning.md) — sweeps generate many runs that require tracking to compare
- [Data Versioning](data-versioning.md) — experiments must link to the data version they were trained on
- [Cross-Validation](cross-validation.md) — cross-validation runs multiple training folds that benefit from experiment tracking

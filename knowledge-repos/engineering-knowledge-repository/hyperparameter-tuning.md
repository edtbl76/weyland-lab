---
id: hyperparameter-tuning
tags: [methodology, ai-ml, backend]
surfaces-at: [application-design, code-generation]
related: [experiment-tracking, cross-validation, mlops, fine-tuning]
complexity: intermediate
---

# Hyperparameter Tuning

## What It Is
The process of finding the optimal configuration of model hyperparameters — values that are set before training and not learned from data (learning rate, batch size, number of layers, regularization strength, tree depth). Unlike model parameters (weights), hyperparameters control the training process itself. Poorly chosen hyperparameters lead to underfitting, overfitting, or slow convergence. Systematic tuning is essential for extracting maximum model performance.

## When to Apply
- After establishing a working baseline model — tune after you have something that trains
- Before concluding a model architecture is insufficient — hyperparameter tuning often yields larger gains than architecture changes
- As part of the standard ML workflow for any model being deployed to production

## Key Concepts
- **Grid Search**: Exhaustively evaluate all combinations of a predefined hyperparameter grid. Guaranteed to find the best combination in the grid; exponentially expensive with more hyperparameters. Use only for ≤ 3 hyperparameters with small grids
- **Random Search**: Sample hyperparameter combinations randomly from defined distributions. Surprisingly effective — finds good solutions faster than grid search for high-dimensional spaces (Bergstra & Bengio, 2012). The practical baseline
- **Bayesian Optimization**: Build a probabilistic model of the objective function (model performance vs. hyperparameters) and use it to intelligently select the next hyperparameter combination to evaluate. Significantly more efficient than random search for expensive-to-evaluate models. Optuna and W&B Sweeps implement this
- **Optuna**: The leading open-source hyperparameter optimization framework — Bayesian optimization, pruning (stop bad trials early), integration with MLflow and W&B
- **Early Stopping in Sweeps**: Terminate poorly performing trials before completion — saves significant compute. Optuna's pruners and Hyperband implement this
- **Key Hyperparameters by Model Type**:
  - Neural networks: learning rate (most important), batch size, dropout, weight decay, architecture depth/width
  - Fine-tuning LLMs: learning rate (critical), LoRA rank, warmup steps, epochs (critical — often just 1-3)
  - Gradient boosted trees (XGBoost/LightGBM): n_estimators, max_depth, learning rate, min_child_samples, subsample
- **Learning Rate is Almost Always the Most Important**: Start hyperparameter tuning with the learning rate. A well-chosen learning rate often matters more than all other hyperparameter choices combined
- **Cross-Validation for Tuning**: Use k-fold cross-validation as the evaluation function during tuning — reduces variance in the performance estimate and avoids overfitting to a single validation split
- **Warm Starting**: Initialize a new tuning run from the best configuration found in a previous run — faster convergence than starting from scratch

## In Practice
Method ML hyperparameter tuning uses Optuna with tree-structured Parzen estimator (TPE) as the sampler and MedianPruner for early stopping. All tuning runs are logged in MLflow. Learning rate is always included in the search space. For LLM fine-tuning, learning rate and number of epochs are the primary tuning targets.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Hyperparameter Tuning**: Don't grid search — use random search as the baseline and Bayesian optimization (Optuna) for expensive models. Learning rate is almost always the most impactful hyperparameter — always include it in your search space. Use early stopping (Hyperband/MedianPruner) to kill bad trials fast. Log every trial in experiment tracking — the full history informs future tuning runs. For fine-tuning LLMs, learning rate and epochs are the critical parameters; LoRA rank is secondary. Cross-validate during tuning to get reliable performance estimates. → `engineering-knowledge-repository/hyperparameter-tuning.md`

## Related Entries
- [Experiment Tracking](experiment-tracking.md) — every hyperparameter tuning trial must be logged
- [Cross-Validation](cross-validation.md) — cross-validation provides reliable performance estimates during tuning
- [MLOps](mlops.md) — hyperparameter tuning is part of the automated training pipeline
- [Fine-Tuning](fine-tuning.md) — LLM fine-tuning hyperparameters (learning rate, epochs) are especially critical

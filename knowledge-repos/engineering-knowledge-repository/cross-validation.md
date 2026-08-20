---
id: cross-validation
tags: [methodology, ai-ml, backend]
surfaces-at: [application-design, code-generation]
related: [hyperparameter-tuning, model-evaluation-metrics, class-imbalance, feature-engineering, experiment-tracking]
complexity: intermediate
---

# Cross-Validation

## What It Is
A model evaluation technique that estimates how well a model generalizes to unseen data by training and evaluating on multiple different splits of the available data. A single train/test split produces a high-variance performance estimate that depends heavily on which examples happen to land in each split. Cross-validation averages performance across multiple splits, producing a more reliable estimate of true generalization performance.

## When to Apply
- Evaluating model performance when dataset size is limited
- During hyperparameter tuning — use CV as the objective function
- Comparing multiple models or feature sets — CV produces more reliable rankings
- Any time a single validation split would produce noisy estimates

## Key Concepts
- **K-Fold Cross-Validation**: Split data into K folds; train on K-1 folds, evaluate on the held-out fold; repeat K times; average the K scores. K=5 or K=10 is standard. Produces K times as many training runs
- **Stratified K-Fold**: Preserves the class distribution in each fold — required for classification tasks, especially with class imbalance. The default choice for classification
- **Leave-One-Out (LOO)**: K equals the number of samples — each sample is the validation set once. Maximum use of data; computationally expensive; rarely used beyond small datasets
- **Time Series CV**: Standard CV shuffles data, which leaks future information in temporal settings. Use `TimeSeriesSplit` — train on past, evaluate on future. Maintain temporal ordering strictly
- **Nested CV**: Outer loop estimates generalization performance; inner loop performs hyperparameter tuning. Prevents overfitting to the validation set during tuning. Required for unbiased evaluation when tuning hyperparameters
- **CV During Preprocessing**: Feature engineering transformations (scalers, encoders) must be fit inside each CV fold on training data and applied to the validation fold — fitting on all data before CV leaks statistics and inflates estimates
- **Variance of CV Estimates**: K-fold CV still has variance. Repeated K-fold (run K-fold multiple times with different random splits, average all results) reduces variance further — used when a stable estimate matters more than compute cost
- **scikit-learn**: `cross_val_score`, `cross_validate`, `StratifiedKFold`, `TimeSeriesSplit`, `Pipeline` — the standard toolkit. Using `Pipeline` inside CV is critical to prevent leakage

## In Practice
Method ML evaluations default to stratified 5-fold CV for classification and standard 5-fold for regression. Time series tasks use `TimeSeriesSplit`. All preprocessing is wrapped in scikit-learn `Pipeline` objects to prevent CV leakage. Hyperparameter tuning (Optuna) uses CV as the objective function. CV results are logged in MLflow.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Cross-Validation**: A single train/test split lies — it gives you one lucky or unlucky draw. Use stratified k-fold (K=5 or 10) for a reliable performance estimate. For time series data, use TimeSeriesSplit — never shuffle temporal data. Wrap all preprocessing in a Pipeline before CV — leaking fit statistics from the full dataset into CV folds artificially inflates your metrics. Use nested CV when tuning hyperparameters to avoid overfitting to the validation set. Log CV fold results, not just the mean. → `engineering-knowledge-repository/cross-validation.md`

## Related Entries
- [Hyperparameter Tuning](hyperparameter-tuning.md) — CV is the evaluation function used during hyperparameter tuning
- [Model Evaluation Metrics](model-evaluation-metrics.md) — CV produces the estimates of model evaluation metrics
- [Class Imbalance](class-imbalance.md) — stratified k-fold is required to preserve class distributions across folds
- [Feature Engineering](feature-engineering.md) — feature engineering must be performed inside CV folds to prevent leakage
- [Experiment Tracking](experiment-tracking.md) — CV results (per-fold scores, mean, std) should be logged in experiment tracking

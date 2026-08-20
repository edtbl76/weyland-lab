---
id: ensemble-methods
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [hyperparameter-tuning, cross-validation, model-evaluation-metrics, feature-engineering, class-imbalance]
complexity: intermediate
---

# Ensemble Methods

## What It Is
Techniques that combine multiple ML models to produce predictions better than any single model. Ensembles work because individual models make different errors — combining predictions cancels out individual errors and reduces variance. Ensemble methods underpin the most powerful classical ML algorithms (Random Forest, XGBoost, LightGBM) and are a standard technique for squeezing the last few percentage points of performance in production systems and ML competitions.

## When to Apply
- Maximizing predictive performance when a single model falls short
- Reducing prediction variance on noisy datasets
- Kaggle competitions and production systems where performance matters most
- When you have multiple trained models and want to combine their strengths

## Key Concepts
- **Bagging (Bootstrap Aggregating)**: Train multiple models on different random subsamples of the training data (with replacement); average their predictions. Reduces variance without increasing bias. Random Forest is bagging applied to decision trees
- **Random Forest**: An ensemble of decision trees trained on bootstrapped data samples, each considering a random subset of features at each split. Robust, fast to train, handles high-dimensional data well. Strong baseline for tabular classification and regression
- **Boosting**: Train models sequentially, each correcting the errors of the previous. Focuses learning on hard examples. Typically outperforms bagging. Three dominant implementations:
  - *XGBoost*: Gradient boosted trees with regularization, built-in cross-validation, handles missing values. Industry standard for tabular data
  - *LightGBM*: Faster than XGBoost for large datasets via leaf-wise tree growth and histogram-based splits. Often the top choice for large tabular datasets
  - *CatBoost*: Handles categorical features natively without encoding. Strong for datasets with many categorical columns
- **Stacking (Stacked Generalization)**: Train a meta-model on the out-of-fold predictions of base models. The meta-model learns how to best combine the base model predictions. More powerful than simple averaging; requires careful CV implementation to prevent leakage
- **Voting / Averaging**: Hard voting (majority vote for classification), soft voting (average predicted probabilities), averaging regression predictions. Simple but effective when models have complementary error patterns
- **Blending**: Train base models on a training set; train meta-model on a holdout set predictions. Simpler than stacking but uses less data for training
- **Diversity is Required**: Ensembles only work if member models make different errors. Combining five identical models adds nothing. Diversity sources: different algorithms, different hyperparameters, different feature subsets, different training data subsets

## In Practice
Method uses LightGBM as the primary gradient boosted tree model for tabular tasks. XGBoost is used when interpretability with SHAP is important (TreeSHAP is faster for XGBoost). Stacking ensembles are used for high-stakes competition-style modeling. Simple averaging across 3-5 diverse model types is used as a performance booster when marginal gains justify the operational complexity.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Ensemble Methods**: For tabular data, start with LightGBM — a single well-tuned gradient boosted tree often beats complex ensembles with far less operational overhead. Add Random Forest to a voting ensemble when you need variance reduction. Stacking is powerful but requires proper out-of-fold predictions to prevent leakage — never train the meta-model on the same data as base models. Ensemble diversity is the mechanism — five copies of the same model do nothing. In production, weigh the 1-2% accuracy gain from a complex ensemble against the operational cost of maintaining multiple models. → `engineering-knowledge-repository/ensemble-methods.md`

## Related Entries
- [Hyperparameter Tuning](hyperparameter-tuning.md) — each ensemble member requires hyperparameter tuning
- [Cross-Validation](cross-validation.md) — stacking requires out-of-fold CV predictions to prevent leakage
- [Model Evaluation Metrics](model-evaluation-metrics.md) — ensemble performance is validated against single-model baselines
- [Feature Engineering](feature-engineering.md) — strong features benefit ensemble members individually and collectively
- [Class Imbalance](class-imbalance.md) — balanced bagging variants address class imbalance within ensemble frameworks

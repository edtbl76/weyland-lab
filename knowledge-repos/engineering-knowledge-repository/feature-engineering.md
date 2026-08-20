---
id: feature-engineering
tags: [methodology, ai-ml, data, backend]
surfaces-at: [functional-design, application-design]
related: [data-augmentation, class-imbalance, cross-validation, training-serving-skew, feature-stores, ml-pipelines]
complexity: intermediate
---

# Feature Engineering

## What It Is
The process of transforming raw data into informative features that improve machine learning model performance. Feature engineering bridges the gap between raw data and model inputs — selecting, transforming, combining, and creating variables that capture the signal the model needs to learn the target. In classical ML (non-deep learning), feature engineering is often the single highest-leverage activity. Deep learning reduces but does not eliminate the need for feature engineering.

## When to Apply
- Classical ML models (linear models, gradient boosted trees, SVMs) — feature engineering is critical
- Before applying any ML algorithm to structured/tabular data
- When model performance is below target — often feature engineering yields larger gains than algorithm changes
- Any time domain knowledge can inform how to represent the data

## Key Concepts
- **Numerical Features**: Scaling (StandardScaler, MinMaxScaler), log transforms for skewed distributions, binning continuous variables, polynomial features for capturing non-linearity
- **Categorical Features**: One-hot encoding (low cardinality), target encoding (high cardinality with leakage risk), ordinal encoding when order matters, embedding lookup for very high cardinality
- **Missing Value Handling**: Mean/median/mode imputation, indicator flag for missingness pattern, model-based imputation, drop if missing rate is high
- **Feature Selection**: Remove zero-variance features; correlation analysis to remove redundant features; permutation importance to identify high-value features; LASSO regularization for automatic feature selection
- **Feature Interaction**: Create product features (A × B), ratio features (A / B), difference features — captures relationships not visible to linear models
- **Temporal Features**: Extract hour, day-of-week, month, holiday flags, days-since-event from timestamps. Lag features and rolling aggregates for time series
- **Text Features**: TF-IDF, bag-of-words, character n-grams for classical ML text tasks. For deep learning: use embeddings instead
- **Target Leakage**: A feature that encodes future information or is derived from the target — causes artificially high training performance and catastrophic production failure. Common with temporal data. Review every feature for temporal validity
- **Train/Test Split Before Feature Engineering**: Fit scalers and encoders on train data only; apply (transform) to test data. Fitting on the full dataset leaks test statistics into training — inflates performance estimates

## In Practice
Method ML pipelines use scikit-learn Pipeline objects to chain preprocessing and model steps — prevents train/test leakage. Feature importance from LightGBM/XGBoost is used post-training to prune low-signal features. Target encoding uses cross-validation folds to avoid leakage. All transformers are versioned and serialized with the model artifact.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Feature Engineering**: Feature quality beats algorithm complexity for tabular data — garbage in, garbage out. Fit preprocessing (scalers, encoders) on train data only and transform test data — leaking test statistics into training causes overoptimistic metrics. Use target encoding carefully — it leaks signal if not done within CV folds. Check every feature for temporal leakage before any time-sensitive task. Use scikit-learn Pipelines to package preprocessing with the model. After training, use feature importance to remove low-signal noise. → `engineering-knowledge-repository/feature-engineering.md`

## Related Entries
- [Data Augmentation](data-augmentation.md) — augmentation and feature engineering are complementary dataset improvement strategies
- [Class Imbalance](class-imbalance.md) — feature engineering can include engineered features that help with imbalanced targets
- [Cross-Validation](cross-validation.md) — feature engineering must be performed inside CV folds to prevent leakage
- [Training-Serving Skew](training-serving-skew.md) — feature transformations must match exactly between training and serving
- [Feature Stores](feature-stores.md) — feature stores operationalize engineered features for reuse across models
- [ML Pipelines](ml-pipelines.md) — feature engineering steps are embedded in ML pipelines

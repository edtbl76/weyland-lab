---
id: class-imbalance
tags: [pattern, ai-ml, data, backend]
surfaces-at: [functional-design, application-design]
related: [data-augmentation, feature-engineering, model-evaluation-metrics, cross-validation]
complexity: intermediate
---

# Class Imbalance

## What It Is
A condition in classification datasets where one class (the majority class) significantly outnumbers another (the minority class). Common in fraud detection (0.1% fraud), medical diagnosis (rare disease), churn prediction, and anomaly detection. A model trained on imbalanced data without correction learns to predict the majority class almost exclusively — achieving high accuracy while being useless for the problem it was trained to solve.

## When to Apply
- Any classification task where class proportions are unequal (rule of thumb: ratio > 1:10 warrants action)
- Binary and multi-class classification problems
- When precision-recall tradeoff matters more than overall accuracy

## Key Concepts
- **Accuracy is Misleading**: A dataset with 99% negatives achieves 99% accuracy by predicting all-negative. Use precision, recall, F1, AUC-PR, or Matthews Correlation Coefficient instead — accuracy is useless as an imbalance metric
- **Resampling — Oversampling**: Duplicate minority class examples (random oversampling) or generate synthetic examples (SMOTE) — increases minority class representation. Oversample training data only; never oversample validation or test sets
- **SMOTE (Synthetic Minority Oversampling Technique)**: Generates synthetic minority examples by interpolating between existing minority examples in feature space. Reduces overfitting compared to simple duplication. Primary technique for tabular data imbalance
- **Resampling — Undersampling**: Remove majority class examples to balance. Simpler than oversampling but discards potentially useful data. Only viable when the majority class is large enough to survive reduction
- **Class Weights**: Most classifiers (scikit-learn, XGBoost) support `class_weight='balanced'` — internally upweights minority class losses during training without changing the data. Often the simplest and most effective approach
- **Threshold Tuning**: Classification models output probabilities; the default 0.5 threshold may not be optimal for imbalanced problems. Tune the classification threshold using precision-recall curves on validation data
- **Focal Loss**: A loss function modification (from object detection) that down-weights easy majority class examples and focuses training on hard minority class examples. Used in deep learning
- **Ensemble Methods**: BalancedRandomForest, EasyEnsemble — combine bagging with resampling to improve minority class detection
- **Stratified Sampling**: In cross-validation and train/test splits, ensure each fold preserves the original class ratio — `StratifiedKFold` in scikit-learn. Critical for reliable evaluation on imbalanced datasets

## In Practice
Method's default for tabular classification imbalance: try `class_weight='balanced'` first (zero data modification, often sufficient). If that's insufficient, apply SMOTE on the training fold within CV. Evaluation always uses AUC-PR and F1 rather than accuracy. Threshold is tuned post-training on a held-out validation set.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Class Imbalance**: Accuracy is a trap — a model that predicts all-majority is worthless at 99% accuracy. Use AUC-PR, F1, or MCC for imbalanced problems. Start with class_weight='balanced' — it's free and often enough. If not, apply SMOTE on training data only (never on validation/test). Tune the classification threshold using the precision-recall curve rather than accepting the 0.5 default. Always use stratified k-fold CV to ensure reliable performance estimates. → `engineering-knowledge-repository/class-imbalance.md`

## Related Entries
- [Data Augmentation](data-augmentation.md) — augmentation (including SMOTE) is the primary technique for expanding minority class data
- [Feature Engineering](feature-engineering.md) — engineered features can help models distinguish minority class examples
- [Model Evaluation Metrics](model-evaluation-metrics.md) — imbalanced problems require precision, recall, F1, AUC-PR rather than accuracy
- [Cross-Validation](cross-validation.md) — stratified k-fold CV is required for reliable evaluation on imbalanced datasets

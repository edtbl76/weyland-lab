---
id: anomaly-detection
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [model-evaluation-metrics, class-imbalance, time-series-forecasting, model-monitoring, data-drift]
complexity: intermediate
---

# Anomaly Detection

## What It Is
The identification of data points, events, or patterns that deviate significantly from expected behavior. Anomaly detection underpins fraud detection, infrastructure monitoring, quality control, intrusion detection, and predictive maintenance. It is distinct from standard classification because anomalies are rare by definition — labeled examples are scarce, and the distribution of "normal" is far better understood than the distribution of "anomalous." This shapes both algorithm selection and evaluation strategy.

## When to Apply
- Fraud detection — identify transactions that deviate from user behavior patterns
- Infrastructure and application monitoring — detect unusual metrics, error spikes, latency outliers
- Quality control — identify defective items in manufacturing or data pipelines
- Cybersecurity — network intrusion detection, unusual access patterns
- Predictive maintenance — detect equipment behavior that precedes failure

## Key Concepts
- **Unsupervised Anomaly Detection**: No labeled anomaly examples required — learn the distribution of normal data and flag significant deviations. Suitable when labeled anomalies are unavailable or too rare
  - *Isolation Forest*: Randomly partitions data; anomalies are isolated in fewer splits. Fast, scalable, effective for tabular data. The practical default for unsupervised tabular anomaly detection
  - *One-Class SVM*: Learns a boundary around normal data; points outside are anomalies. Sensitive to hyperparameters; slower than Isolation Forest
  - *Autoencoder*: Neural network trained to reconstruct normal data; anomalies have high reconstruction error. Effective for high-dimensional data (images, time series)
- **Semi-Supervised Anomaly Detection**: Train on normal data only; label a small number of confirmed anomalies for threshold calibration
- **Supervised Anomaly Detection**: Treat as classification with severe class imbalance. Use when labeled anomaly examples are available. Apply class imbalance techniques (SMOTE, class weights)
- **Statistical Methods**: Z-score (standard deviations from mean), IQR (interquartile range) outlier bounds — simple baselines; work well for univariate, normally distributed data
- **Time Series Anomaly Detection**: Point anomalies, contextual anomalies (normal value, abnormal context), collective anomalies (abnormal sequences). Libraries: Prophet (Facebook), PyOD, ADTK
- **Evaluation Challenges**: Standard accuracy is meaningless for rare anomalies. Use precision, recall, F1 at the operating threshold, AUC-PR. Define the business cost of false positives (alert fatigue) vs. false negatives (missed anomalies) — tune the threshold accordingly
- **Threshold Tuning**: Anomaly detectors output a score, not a binary label. The threshold converts score to decision. Too low = alert fatigue; too high = missed anomalies. Tune on a labeled validation set or via business constraint

## In Practice
Method uses Isolation Forest as the default for tabular unsupervised anomaly detection. Autoencoders are used for time series and high-dimensional anomaly detection. Evaluation uses AUC-PR and threshold analysis against labeled validation data. Alert thresholds are tuned to target acceptable false positive rates.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Anomaly Detection**: Start with Isolation Forest for tabular data — it's fast, effective, and requires no labeled anomalies. Evaluate with AUC-PR and precision/recall at the operating threshold — not accuracy. Tune your score threshold based on the false positive / false negative cost tradeoff for your use case: alert fatigue is a real failure mode. For time series, distinguish point anomalies from contextual anomalies — they require different detection approaches. When labeled anomaly examples exist, treat it as a severe class imbalance problem rather than unsupervised detection. → `engineering-knowledge-repository/anomaly-detection.md`

## Related Entries
- [Model Evaluation Metrics](model-evaluation-metrics.md) — AUC-PR and threshold analysis are the correct metrics for anomaly detection
- [Class Imbalance](class-imbalance.md) — supervised anomaly detection is a class imbalance problem
- [Time Series Forecasting](time-series-forecasting.md) — time series anomaly detection requires temporal-aware approaches
- [Model Monitoring](model-monitoring.md) — anomaly detection is applied to model performance metrics for production monitoring
- [Data Drift](data-drift.md) — data drift detection uses statistical anomaly detection on feature distributions

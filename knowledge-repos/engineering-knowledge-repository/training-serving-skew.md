---
id: training-serving-skew
tags: [anti-pattern, ai-ml, data, backend]
surfaces-at: [application-design, functional-design]
related: [feature-stores, data-drift, model-monitoring, feature-engineering, mlops]
complexity: intermediate
---

# Training-Serving Skew

## What It Is
The divergence between the features used to train a model and the features computed and served at inference time. Training-serving skew is one of the most common and insidious causes of ML model degradation — the model was trained on correct features but production inference uses slightly different values due to implementation differences, data pipeline inconsistencies, or timing mismatches. The model is technically "working" — it's just answering a subtly different question than it was trained on.

## When to Apply
- Prevention: design consideration for every ML system
- Detection: model monitoring investigation when performance degrades without obvious cause

## Key Concepts
- **Root Causes**:
  - *Transformation divergence*: The feature computation code was written twice — once in Python for training, once in Java/Go/SQL for serving. Subtle differences in handling nulls, edge cases, or floating-point precision accumulate
  - *Data freshness mismatch*: Training used features computed from data up to time T. Serving uses real-time features that include data from T+latency. Or vice versa — serving uses stale features
  - *Data source mismatch*: Training pulled from the data warehouse (backfilled, cleaned, deduplicated). Serving reads from the production database (raw, real-time, slightly different schema)
  - *Missing feature pipeline*: A feature was logged during training but the logging was removed or changed before production. Serving sends nulls or defaults where training had real values

- **Feature Store as the Solution**: A feature store runs the same computation logic for offline (training) and online (serving) — eliminating transformation divergence by design. The feature pipeline is written once

- **Log and Replay**: Log all features at serving time. Periodically replay logged serving features through the model and compare predictions against training predictions on the same inputs. Detect skew before it causes visible degradation

- **Training on Production Features**: Train on features logged from production (point-in-time correct) rather than recomputed historical features. Eliminates source mismatch

- **Parity Tests**: Automated tests that run the same input through the training feature pipeline and the serving feature pipeline and assert the outputs are identical (within floating-point tolerance)

- **Distribution Comparison**: Compare feature distributions at training time vs. serving time using the same drift detection techniques as data drift monitoring. Skew shows up as a distribution shift

## In Practice
Method ML systems prevent training-serving skew through: feature stores (primary prevention), parity tests in CI (training vs. serving pipeline comparison on sample inputs), and distribution monitoring in production (serving features compared against training distributions). When skew is detected, root cause analysis traces the divergence to the specific feature and pipeline component.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Training-Serving Skew**: The model was trained on one thing and is answering a different question in production. The most common cause: feature transformations written twice (once for training, once for serving) with subtle differences. Prevention: feature store (one computation, two stores). Detection: parity tests (assert training and serving pipelines produce identical output on the same input), distribution monitoring (compare serving features against training distributions). Skew is silent — it doesn't throw errors; it just makes predictions worse. → `engineering-knowledge-repository/training-serving-skew.md`

## Related Entries
- [Feature Stores](feature-stores.md) — the primary architectural solution to training-serving skew
- [Data Drift](data-drift.md) — skew can appear as apparent data drift in monitoring
- [Model Monitoring](model-monitoring.md) — monitoring detects skew-induced degradation
- [Feature Engineering](feature-engineering.md) — skew originates in feature transformation code written for training
- [MLOps](mlops.md) — preventing training-serving skew is an MLOps engineering discipline

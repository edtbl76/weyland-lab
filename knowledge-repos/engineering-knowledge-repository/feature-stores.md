---
id: feature-stores
tags: [pattern, ai-ml, data, backend, distributed-systems]
surfaces-at: [application-design, infrastructure-design]
related: [mlops, training-serving-skew, data-drift, feature-engineering, continuous-training, data-versioning]
complexity: advanced
---

# Feature Stores

## What It Is
A centralized platform for storing, managing, and serving ML features — computed representations of raw data used for both model training and real-time serving. Feature stores have two components: an offline store (for historical features used in training) and an online store (for low-latency feature retrieval at inference time). The central value: features are computed once, reused across multiple models, and guaranteed consistent between training and serving.

## When to Apply
- Multiple ML models that share common features (user profile features, item embeddings, transaction history)
- When training-serving skew is causing production model degradation
- Organizations with multiple data science teams that are duplicating feature computation
- Real-time ML serving requiring sub-100ms feature retrieval

## When Not to Apply
- Single-model systems where feature complexity is low — a feature store adds significant infrastructure overhead
- Batch-only inference where online serving latency is not a constraint

## Key Concepts
- **Offline Store**: Historical feature data stored in a columnar format (S3 + Parquet, Redshift, BigQuery). Used to generate training datasets via point-in-time correct joins — ensuring features reflect what was known at prediction time, not future data
- **Online Store**: Low-latency key-value store (Redis, DynamoDB, Cassandra) serving the latest feature values at inference time. Millisecond retrieval
- **Point-in-Time Correct Joins**: Training data must use features that were available at the time of the label, not future values. Feature stores handle this automatically — a major source of data leakage if done manually
- **Training-Serving Consistency**: The feature store guarantees the same feature computation logic runs offline (training) and online (serving). Without a feature store, slight differences in transformation code between training and serving cause skew
- **Feature Pipeline**: The computation that produces features from raw data — runs periodically or in real-time (streaming) to keep the online store fresh
- **Feature Reuse**: A feature computed once (e.g., "user's 30-day purchase count") can be consumed by multiple models without duplication. The feature store is a shared feature library
- **Feature Versioning**: Features evolve over time — the feature store tracks versions so models can pin to the feature version they were trained on
- **Feast**: The leading open-source feature store — supports offline (S3/BigQuery) and online (Redis/DynamoDB) stores, Python SDK, and point-in-time correct retrieval
- **Tecton**: Managed feature store with real-time streaming feature computation. Enterprise-grade; higher cost
- **Vertex AI Feature Store**: GCP's managed feature store — integrated with Vertex AI training and serving pipelines

## In Practice
Method ML systems introduce a feature store when two or more models share features or when training-serving skew is identified as a quality issue. Feast with Redis (online) and S3/Parquet (offline) is the default for self-managed deployments. Feature pipelines run on Airflow. Point-in-time correct training dataset generation is used for all time-sensitive features.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Feature Stores**: The primary value is consistency — the same feature computation runs at training time and serving time, eliminating training-serving skew. Secondary value: reuse features across models without duplication. An online store (Redis) serves features at <10ms for real-time inference; an offline store (S3 + Parquet) generates training datasets with point-in-time correct joins. Add a feature store when skew is causing model degradation or when multiple models share features. Feast is the open-source default. Don't introduce one for a single simple model. → `engineering-knowledge-repository/feature-stores.md`

## Related Entries
- [MLOps](mlops.md) — feature stores are advanced MLOps infrastructure
- [Training-Serving Skew](training-serving-skew.md) — feature stores are the primary solution to training-serving skew
- [Data Drift](data-drift.md) — feature stores enable drift detection by tracking feature distribution over time
- [Feature Engineering](feature-engineering.md) — feature stores operationalize and share the output of feature engineering
- [Continuous Training](continuous-training.md) — CT pipelines pull training datasets from the offline feature store
- [Data Versioning](data-versioning.md) — feature stores version features alongside datasets

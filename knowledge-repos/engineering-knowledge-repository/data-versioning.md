---
id: data-versioning
tags: [methodology, ai-ml, data, backend]
surfaces-at: [application-design, infrastructure-design]
related: [mlops, experiment-tracking, feature-stores, continuous-training, data-drift]
complexity: intermediate
---

# Data Versioning

## What It Is
The practice of tracking and versioning datasets used for ML training, evaluation, and serving — analogous to Git for code. Without data versioning, experiments are not reproducible (you can't recreate the exact dataset used to train a model), data lineage is lost, and debugging regressions is nearly impossible. Data versioning links each model version to the exact dataset it was trained on.

## When to Apply
- Any ML project that trains models on data that changes over time
- Before the first production training run — add data versioning before you need it
- When multiple team members share training datasets

## Key Concepts
- **DVC (Data Version Control)**: The dominant open-source data versioning tool. Works alongside Git — stores data files in remote storage (S3, GCS) and tracks metadata (checksums, paths) in Git. `dvc add data.csv` → commits a `.dvc` pointer file to Git; actual data goes to remote storage
- **Delta Lake / Apache Iceberg**: Table versioning formats for large-scale data — every write creates a new snapshot with time travel queries. `SELECT * FROM table VERSION AS OF timestamp`. Used for large datasets in data lakehouse architectures
- **Dataset Snapshots**: Point-in-time copies of a dataset linked to a training run. Enables exact reproduction of any historical training run
- **Lineage Tracking**: Recording where data came from — source systems, transformations applied, labeling pipeline version. Essential for debugging data quality issues
- **Train/Val/Test Split Versioning**: The split itself must be versioned — using the same split across experiments ensures valid comparison. Leaking test data into training is the most common ML evaluation error
- **Schema Versioning**: Track changes to dataset schema — added features, renamed columns, type changes. Schema changes can silently break training pipelines
- **Data Validation Before Versioning**: Run data validation (Great Expectations, Pandera) before creating a new version — catch schema violations, null rates, and distribution anomalies before they contaminate training data
- **Linking Data to Experiments**: Every experiment tracking run should log the DVC commit hash or Delta Lake snapshot version — the three-way link (code + data + model) is the reproducibility requirement

## In Practice
Method ML projects use DVC for dataset versioning with S3 as the remote store. DVC commit hashes are logged in every MLflow experiment run. Train/val/test splits are committed as versioned artifacts, not regenerated per run. Great Expectations validates data quality before each new version is committed.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Versioning**: A model is only reproducible if you can recreate the exact dataset it was trained on. DVC is the standard tool — add data files to DVC, commit the `.dvc` pointer to Git, push data to S3. Log the DVC hash in every experiment run. Version your train/val/test splits as artifacts — don't regenerate them. Run data validation before committing new versions. Link every training run to code version + data version + hyperparameters — all three are required for reproducibility. → `engineering-knowledge-repository/data-versioning.md`

## Related Entries
- [MLOps](mlops.md) — data versioning is one of the three versioning axes of MLOps
- [Experiment Tracking](experiment-tracking.md) — experiments must record the data version they trained on
- [Feature Stores](feature-stores.md) — feature stores version feature data alongside model artifacts
- [Continuous Training](continuous-training.md) — CT pipelines consume versioned data snapshots
- [Data Drift](data-drift.md) — comparing data versions over time reveals drift

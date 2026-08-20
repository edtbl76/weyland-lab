---
id: ml-pipelines
tags: [pattern, ai-ml, deployment, backend, distributed-systems]
surfaces-at: [infrastructure-design, application-design]
related: [mlops, continuous-training, feature-stores, data-versioning, model-registry, asynchronous-processing]
complexity: intermediate
---

# ML Pipelines

## What It Is
Orchestrated, automated sequences of steps that transform raw data into deployed ML models. A training pipeline typically covers: data ingestion → validation → feature engineering → training → evaluation → registration. A serving pipeline covers: feature retrieval → preprocessing → inference → post-processing → logging. ML pipelines make training reproducible, enable continuous training, and allow individual steps to be independently versioned, tested, and scaled.

## When to Apply
- Any ML system beyond initial experimentation — once you train a model more than twice, automate the pipeline
- Multi-step workflows where intermediate outputs need caching, parallelism, or independent retries
- Teams that need to share training infrastructure across multiple model projects

## Key Concepts
- **Pipeline Steps**: Each step is a discrete, containerized unit — receives inputs (data files, parameters), produces outputs (transformed data, model artifacts), and runs in isolation. Steps can be run in parallel or sequence
- **DAG (Directed Acyclic Graph)**: Pipeline steps and their dependencies form a DAG — the orchestrator schedules steps in topological order, running independent steps in parallel
- **Parameterization**: Pipelines accept parameters (hyperparameters, data versions, feature subsets) at run time — enabling the same pipeline to serve experiment runs, scheduled CT, and manual one-offs
- **Step Caching**: If a step's inputs haven't changed since the last run, reuse the cached output. Dramatically speeds up iterative development — only rerun affected downstream steps
- **Airflow**: The dominant workflow orchestration platform. DAGs defined in Python. Excellent for data pipeline orchestration; not ML-specific but widely used
- **Kubeflow Pipelines**: Kubernetes-native ML pipeline platform. Pipeline steps run as containers in Kubernetes — natively scales. Domain-specific: steps produce ML-typed artifacts
- **Metaflow**: ML-focused pipeline framework from Netflix. Python-native, minimal boilerplate, integrates with AWS Step Functions for production
- **Prefect / Dagster**: Modern data orchestration platforms with better DX than Airflow — dynamic DAGs, reactive scheduling, built-in observability
- **Artifact Store**: Pipeline artifacts (datasets, model files, metrics) are stored and versioned — each pipeline run produces a new set of versioned artifacts
- **Trigger Mechanisms**: Pipelines are triggered by schedule (cron), event (new data available), or manual invocation. CT pipelines use drift and performance triggers

## In Practice
Method ML projects use Airflow for training pipelines in AWS environments, Kubeflow for Kubernetes-native systems, and Metaflow for Python-first teams wanting minimal infrastructure overhead. All pipeline steps are containerized. Step caching is enabled to accelerate iterative development. Pipeline runs are linked to experiment tracking runs via shared run IDs.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — ML Pipelines**: Automate your training pipeline before you train a model for the third time. Containerize each step — it's the boundary for versioning, testing, and independent scaling. Enable step caching — you should only rerun steps whose inputs changed. Parameterize everything — the same pipeline serves experiments, scheduled CT, and manual runs. Airflow is the incumbent; Metaflow has the best Python DX; Kubeflow is the Kubernetes-native choice. Link every pipeline run to experiment tracking so you can trace any model back to the exact pipeline run that produced it. → `engineering-knowledge-repository/ml-pipelines.md`

## Related Entries
- [MLOps](mlops.md) — pipelines are the automation backbone of MLOps
- [Continuous Training](continuous-training.md) — CT is executed as an automated ML pipeline
- [Feature Stores](feature-stores.md) — pipelines pull features from the feature store
- [Data Versioning](data-versioning.md) — pipeline steps consume and produce versioned data artifacts
- [Model Registry](model-registry.md) — pipeline outputs are registered in the model registry
- [Asynchronous Processing](asynchronous-processing.md) — ML pipeline steps are asynchronous, long-running jobs

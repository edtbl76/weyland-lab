---
id: batch-processing
tags: [pattern, backend, data, distributed-systems]
surfaces-at: [application-design, functional-design]
related: [stream-processing, data-pipelines, online-vs-batch-inference, spark]
complexity: beginner
---

# Batch Processing

## What It Is
Processing large volumes of data collected over a period of time in a single scheduled job, rather than processing events as they arrive. Batch processing accumulates data (hourly, daily, weekly) and processes it all at once. It trades latency for throughput — batch jobs process higher data volumes more efficiently than real-time systems, but results are delayed by the batch interval. The traditional foundation of data warehouses, ETL pipelines, and ML training workflows.

## When to Apply
- Processing all historical data (ML training, analytics aggregations, report generation)
- Workloads where latency of hours or days is acceptable
- Complex transformations that are more efficient over large accumulated datasets
- Periodic recomputation of aggregates, rankings, or features

## Key Concepts
- **Scheduled Execution**: Batch jobs run on a schedule — nightly, hourly, or triggered on data arrival. Orchestrated by Airflow, Prefect, or cron
- **Idempotency**: Batch jobs must be safe to rerun — the same input data produces the same output. Required for reliable failure recovery
- **Checkpointing**: For long-running jobs, save intermediate state — enables partial recovery without full restart
- **Apache Spark**: The dominant framework for large-scale distributed batch processing — distributes computation across a cluster. Used for ML feature computation at scale, ETL, and data lake processing
- **Partitioning Strategy**: Partition large datasets by a meaningful dimension (date, region, user_id) — enables parallel processing and incremental updates
- **vs. Stream Processing**: Batch processes bounded, historical datasets on a schedule; stream processing handles unbounded data in real time. Many systems combine both (Lambda/Kappa architectures)

## In Practice
Method uses Apache Spark on AWS EMR for large-scale batch ETL and ML feature computation. Daily batch jobs compute training datasets for model retraining. Airflow schedules and monitors all batch pipelines. Batch jobs are designed to be idempotent and partition-aware for efficient reruns.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Batch Processing**: Use batch when latency requirements allow — batch is simpler and more efficient than streaming for high-volume historical data. Design batch jobs to be idempotent: partition inputs by time or key so reruns are safe and incremental. For batch ML training data preparation at scale, Spark is the standard tool. Track job duration trends — a job that grows from 30 minutes to 4 hours is a scaling problem that will eventually become a production incident. → `engineering-knowledge-repository/batch-processing.md`

## Related Entries
- [Stream Processing](stream-processing.md) — stream processing is the real-time alternative to batch for low-latency requirements
- [Data Pipelines](data-pipelines.md) — batch processing is the execution model for most data pipeline stages
- [Online vs. Batch Inference](online-vs-batch-inference.md) — the same tradeoff applied to ML model inference
- [Spark](spark.md) — Apache Spark is the primary framework for distributed batch processing

---
id: spark
tags: [tooling, backend, data, distributed-systems]
surfaces-at: [application-design, infrastructure-design]
related: [batch-processing, stream-processing, data-pipelines, ml-pipelines]
complexity: intermediate
---

# Apache Spark

## What It Is
A distributed computing framework for large-scale batch and stream data processing. Spark distributes computation across a cluster, processing data in-memory rather than writing intermediate results to disk (unlike Hadoop MapReduce). It is the dominant framework for data engineering workloads that exceed single-machine capacity: large-scale ETL, feature engineering for ML at scale, data lake processing, and machine learning on large datasets (Spark MLlib).

## When to Apply
- Data volumes that exceed single-machine processing capacity
- Large-scale ETL or feature computation jobs (hundreds of GBs to PBs)
- ML training data preparation at scale
- Data lake processing and analytics on object storage (S3, GCS)

## Key Concepts
- **RDD (Resilient Distributed Dataset)**: The low-level distributed collection abstraction. Immutable, partitioned, fault-tolerant. Prefer DataFrames/Dataset API in practice — RDD API is verbose and misses Catalyst optimizations
- **DataFrame / Dataset API**: High-level structured API — similar to pandas/SQL semantics, distributed. Catalyst query optimizer and Tungsten execution engine apply automatic optimizations. The standard Spark API
- **Lazy Evaluation**: Transformations (`filter`, `map`, `join`) are not executed immediately — they build an execution plan. Actions (`count`, `write`, `collect`) trigger execution. Enables optimizer to reorder and combine operations
- **Partitioning**: Data is split into partitions distributed across executor nodes. Partition count determines parallelism. Repartition for joins and writes; partition by date or key for efficient downstream reads
- **Shuffle**: Redistributing data across partitions (for joins, groupBy, repartition) — the most expensive operation in Spark. Minimize shuffles; filter and project early to reduce shuffled data volume
- **Managed Platforms**: AWS EMR, Google Dataproc, Azure HDInsight (managed cluster), Databricks (managed Spark with Delta Lake, notebooks, MLflow integration). Databricks is the leading Spark platform for data + ML teams
- **PySpark**: Python API for Spark — the primary interface for data engineering and ML feature pipelines. Integrates with pandas (Arrow-based conversion) and scikit-learn
- **Delta Lake**: Open-source ACID table format for data lakes (S3/GCS) built on top of Spark — adds ACID transactions, schema enforcement, and time travel to object storage

## In Practice
Method uses Databricks (AWS) for Spark-based data engineering and ML feature computation. PySpark DataFrames for all ETL logic. Delta Lake tables as the storage format for data lake assets. Spark jobs are scheduled via Airflow. Cluster sizing uses autoscaling to match job resource requirements.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Apache Spark**: Use DataFrames, not RDDs — the Catalyst optimizer makes DataFrames dramatically faster for the same logic. Filter and project early to minimize data volume in shuffles. Shuffle (joins, groupBy) is the primary performance bottleneck — profile with Spark UI's stage plan. Partition output by date or entity key for efficient downstream incremental reads. On AWS, Databricks provides Spark with Delta Lake, MLflow, and managed infrastructure that's operationally much simpler than raw EMR. → `engineering-knowledge-repository/spark.md`

## Related Entries
- [Batch Processing](batch-processing.md) — Spark is the primary distributed batch processing framework
- [Stream Processing](stream-processing.md) — Spark Structured Streaming extends Spark to real-time data streams
- [Data Pipelines](data-pipelines.md) — Spark jobs are a core execution engine in data pipeline architectures
- [ML Pipelines](ml-pipelines.md) — Spark MLlib and Spark-based feature computation integrate into ML pipelines

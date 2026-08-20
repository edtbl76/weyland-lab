---
id: database-cost-optimization
tags: [methodology, cost, database, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [cloud-cost-optimization, finops, connection-pooling, database-indexing, read-replicas, data-archiving]
complexity: intermediate
---

# Database Cost Optimization

## What It Is
Techniques for reducing the cost of database infrastructure without sacrificing performance or reliability. Databases are frequently among the top three cloud cost line items — compute, storage, I/O, and data transfer charges compound quickly at scale. Database cost optimization focuses on right-sizing instances, efficient storage management, read/write traffic patterns, and choosing the right database tier for each workload.

## When to Apply
- When database costs are a significant portion of the cloud bill
- Before scaling up database instances — exhaust optimization options first
- When provisioning new database infrastructure — cost-aware design from the start
- Periodic cost reviews as data volume and query patterns evolve

## Key Concepts
- **Right-Sizing**: The most impactful lever. Most databases run on over-provisioned instances. Analyze actual CPU, memory, and IOPS utilization — not peak, but sustained utilization. Downsize if sustained utilization is below 40-50%. Use AWS Compute Optimizer or RDS recommendations
- **Read Replicas for Read Traffic**: Offload read-heavy queries to read replicas rather than scaling the primary. Read replicas cost less than primary instances for equivalent read capacity. Route reporting, analytics, and read-heavy API queries to replicas
- **Storage Tiering**: Move infrequently accessed data to cheaper storage tiers. RDS storage is expensive for cold data — archive old records to S3 (Parquet) and query via Athena at a fraction of the cost. Define a data retention and archiving policy
- **Connection Pooling**: Each database connection consumes memory on the server. Without pooling, microservices with many instances create thousands of connections, forcing larger (more expensive) instances. PgBouncer for PostgreSQL reduces connection count dramatically
- **Query Optimization**: Expensive queries consume more CPU and I/O — directly increasing cost on usage-based database tiers (Aurora Serverless, DynamoDB). Identify and optimize top-cost queries via slow query logs and `EXPLAIN ANALYZE`. Proper indexing reduces I/O per query
- **Aurora Serverless vs. Provisioned**: Aurora Serverless v2 scales to zero and charges per ACU-second — cost-effective for variable or low-traffic workloads. Provisioned Aurora is cheaper at sustained high load. Model expected traffic patterns before choosing
- **DynamoDB Cost Patterns**: On-demand mode costs more per request but scales to zero. Provisioned capacity with auto-scaling is cheaper at predictable load. Avoid hot partitions — they force over-provisioning. Use TTL to automatically delete expired items and reduce storage costs
- **Data Transfer Costs**: Cross-AZ and cross-region data transfer is charged. Colocate application and database in the same AZ where possible. Use VPC endpoints to avoid NAT gateway charges for database traffic
- **Multi-AZ Tradeoffs**: Multi-AZ doubles storage costs for the standby replica. Required for production reliability but evaluate whether dev/staging environments need it

## In Practice
Method conducts database cost reviews at project inception and quarterly thereafter. Read replicas handle all reporting queries. PgBouncer is standard in all PostgreSQL deployments. Data older than 90 days is archived to S3. Instance sizing is reviewed against CloudWatch utilization metrics monthly.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Database Cost Optimization**: Right-sizing is the highest-leverage action — most databases are over-provisioned. Analyze sustained utilization, not peak. Route read traffic to read replicas before scaling the primary. Use PgBouncer for PostgreSQL to reduce connection count and enable smaller instances. Archive cold data to S3 — database storage is 10-50x more expensive than object storage for equivalent data volume. Optimize expensive queries — on usage-based tiers (Aurora Serverless, DynamoDB on-demand), query cost IS infrastructure cost. Disable Multi-AZ on non-production environments. → `engineering-knowledge-repository/database-cost-optimization.md`

## Related Entries
- [Cloud Cost Optimization](cloud-cost-optimization.md) — database cost optimization is a specialization within broader cloud cost management
- [FinOps](finops.md) — database costs should be attributed and visible within the FinOps framework
- [Connection Pooling](connection-pooling.md) — connection pooling reduces database memory pressure, enabling smaller instances
- [Database Indexing](database-indexing.md) — proper indexing reduces I/O per query, directly reducing cost on usage-based tiers
- [Read Replicas](read-replicas.md) — offloading reads to replicas is the primary cost optimization for read-heavy workloads
- [Data Archiving](data-archiving.md) — archiving cold data out of the database reduces storage costs significantly

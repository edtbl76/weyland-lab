---
id: storage-patterns
tags: [pattern, infrastructure, backend, data]
surfaces-at: [infrastructure-design, application-design]
related: [infrastructure-as-code, caching-strategies, data-archiving, cdn, database-cost-optimization]
complexity: intermediate
---

# Storage Patterns

## What It Is
The selection and architectural patterns for cloud storage services — object storage (S3), block storage (EBS), file storage (EFS), and cold/archival storage (Glacier). Each storage type has distinct performance, durability, cost, and access pattern characteristics. Choosing the wrong storage type for a use case is a common source of either excessive cost (over-provisioned block storage for infrequently accessed files) or poor performance (object storage for IOPS-intensive workloads). Understanding when to use each type is foundational infrastructure knowledge.

## When to Apply
- Designing storage for user-uploaded files, application artifacts, logs, or backups
- Replacing costly block storage with cheaper object storage for appropriate workloads
- Evaluating storage for shared file access between multiple compute instances
- Implementing data lifecycle policies to control long-term storage costs

## Key Concepts
- **Object Storage (AWS S3)**:
  - Unstructured data stored as objects (key + value + metadata). Flat namespace; no real directory hierarchy
  - Unlimited capacity; no provisioning required; pay per GB stored + requests
  - Optimized for large files, sequential access, and high throughput — not low-latency random access
  - Use for: application artifacts, user uploads, static web assets, logs, backups, data lake storage, ML training data
  - Durability: 11 nines (99.999999999%). Access via HTTP/HTTPS API or AWS SDK
  - Storage tiers: Standard → Intelligent-Tiering → Standard-IA → Glacier Instant → Glacier Flexible → Deep Archive. Use lifecycle policies to automatically tier aged data
- **Block Storage (AWS EBS)**:
  - Network-attached virtual disk; presents as a block device to an EC2 instance
  - Provisioned IOPS and throughput; low latency (single-digit ms). Required for OS, databases, transactional workloads
  - Tied to an AZ; can only attach to one instance at a time (with exceptions for io2 multi-attach)
  - Use for: OS boot volumes, database data volumes (RDS uses EBS under the hood), application local disk
  - More expensive than S3; pay for provisioned capacity even if unused
- **File Storage (AWS EFS)**:
  - Managed NFS filesystem; mountable from multiple EC2 instances and containers simultaneously
  - Elastic capacity; automatically grows/shrinks. Multi-AZ durable. Slower than EBS (network filesystem latency)
  - Use for: shared code, configuration files, CMS media files, machine learning training data needing POSIX filesystem semantics
  - More expensive than S3; cheaper than equivalent EBS for shared access patterns
- **Archival Storage (S3 Glacier)**:
  - Ultra-low-cost storage for infrequently accessed data with minutes-to-hours retrieval time
  - Use for: compliance archives, regulatory retention, backup cold copies, historical logs
  - Retrieval costs money; evaluate the tradeoff between storage cost savings and retrieval cost when accessed
- **S3 Lifecycle Policies**: Automatically transition objects between storage tiers or expire them based on age or object tags. Example: log files → Standard for 30 days → Standard-IA for 90 days → Glacier for 365 days → delete after 7 years
- **S3 Versioning**: Stores all versions of an object. Protects against accidental deletion and overwrites. Required for compliance data and source-of-truth artifacts. Increases storage costs — use lifecycle policies to expire old versions
- **Pre-Signed URLs**: Time-limited URLs that allow temporary, unauthenticated access to private S3 objects. Use for: secure file download links in applications, direct browser-to-S3 uploads (bypasses your server for large files)
- **Multipart Upload**: S3 requires multipart upload for objects > 5GB; recommended for > 100MB. SDKs handle this automatically but should be explicitly configured for large file uploads

## In Practice
Method uses S3 for all application artifacts, user uploads, logs, and data lake storage. EBS volumes are used only for EC2 OS disks and database storage where managed services (RDS) are not appropriate. EFS is used for shared ML training data and CMS file stores. S3 lifecycle policies tier old logs from Standard to Glacier after 30 days and delete after 365 days. Pre-signed URLs serve user file downloads without routing through application servers.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Storage Patterns**: Default to S3 for any files that don't need a database or low-latency block device — it's durable, scalable, and cheap. Don't use EBS for files your application doesn't need on a local disk; EBS is for databases and OS volumes. Use lifecycle policies to automatically tier aging data to cheaper storage classes — storage cost accumulates silently without them. Pre-signed URLs for file uploads/downloads eliminate your server as a bandwidth bottleneck and reduce egress costs from your application layer. For large file uploads, configure the SDK for multipart upload to avoid timeouts and resume capability. → `engineering-knowledge-repository/storage-patterns.md`

## Related Entries
- [Infrastructure as Code](infrastructure-as-code.md) — storage resources (S3 buckets, EBS volumes) are defined and managed via IaC
- [Caching Strategies](caching-strategies.md) — CDN and application-layer caching reduce repeated S3 access costs
- [Data Archiving](data-archiving.md) — S3 Glacier and lifecycle policies implement data archiving strategies
- [CDN](cdn.md) — static assets served from S3 via CloudFront reduce S3 request costs and improve global latency
- [Database Cost Optimization](database-cost-optimization.md) — storing large blobs in S3 instead of databases is a common cost optimization

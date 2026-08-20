---
id: network-egress-costs
tags: [pattern, cost, cloud, infrastructure, network]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [cloud-cost-optimization, finops, cdn-pattern, kubernetes, database-cost-optimization]
complexity: intermediate
---

# Network Egress Costs

## What It Is
Charges incurred when data transfers out of a cloud provider's network — to the internet, to another region, or (on some providers) between availability zones. Network egress is one of the most frequently underestimated cloud cost drivers. Unlike compute and storage which are visible upfront, egress costs scale silently with traffic and data volume, often appearing as a large and surprising line item. Designing data flows with egress in mind from the start is significantly cheaper than optimizing after the fact.

## When to Apply
- Architecting systems that transfer large volumes of data (media, ML datasets, analytics exports, API responses)
- Multi-region architectures where data crosses regional boundaries
- Microservice architectures where services communicate across AZ boundaries
- Any system where data egress to the internet is a core function

## Key Concepts
- **Egress Pricing Tiers**: Data transfer to the internet is most expensive. Cross-region transfer is moderately expensive. Cross-AZ transfer is cheaper but accumulates at scale. Intra-AZ transfer is typically free. Data ingress (into the cloud) is generally free
- **Cross-AZ Transfer**: AWS charges ~$0.01/GB for cross-AZ data transfer. In a high-throughput microservices architecture, services in different AZs communicating frequently generate material egress costs. Colocate services that communicate heavily in the same AZ, or use topology-aware routing
- **Cross-Region Transfer**: Significantly more expensive than cross-AZ (~$0.02-0.09/GB depending on regions). Avoid unnecessary cross-region data movement. Replicate data regionally where read volume justifies it
- **CDN for Internet Egress**: Serving static assets, media, and cacheable API responses through a CDN (CloudFront, Fastly) dramatically reduces origin egress. CDN egress pricing is typically 40-70% cheaper than direct cloud egress. Every byte served from cache is a byte not charged at origin egress rates
- **VPC Endpoints**: AWS PrivateLink and VPC endpoints route traffic to AWS services (S3, DynamoDB, SQS) through the private AWS network rather than the internet — eliminating NAT gateway data processing charges and reducing egress costs. Replace NAT gateway routes to AWS services with VPC endpoints
- **NAT Gateway Costs**: NAT gateways charge both per-hour and per-GB processed. High-throughput services routing through NAT to AWS services accumulate significant charges. VPC endpoints eliminate this for supported AWS services
- **S3 Transfer Acceleration and Select**: S3 Transfer Acceleration charges a premium for faster uploads. S3 Select reduces egress by filtering data server-side before transfer — pay to transfer only the rows/columns you need rather than the full object
- **Data Export and Analytics**: Exporting large datasets from cloud storage for external analytics is expensive. Query in-place (Athena, BigQuery) rather than exporting. If export is required, compress before transfer
- **Egress Cost Visibility**: Tag and monitor egress costs by service and destination in AWS Cost Explorer. Egress appears under "Data Transfer" — break it down by source service to identify the largest contributors

## In Practice
Method architects review data flow diagrams for cross-AZ and cross-region paths at the infrastructure design stage. CDN fronts all public-facing static and media assets. VPC endpoints replace NAT gateway routes for all supported AWS services. Cross-AZ communication in Kubernetes uses topology-aware routing to prefer same-AZ pod placement. Egress costs are tracked per service in the FinOps dashboard.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Network Egress Costs**: Egress costs are invisible until they're not — track them per service from day one. Serve anything cacheable through a CDN: CDN egress is 40-70% cheaper than origin egress. Replace NAT gateway routes to AWS services with VPC endpoints — eliminates per-GB NAT processing charges entirely. For cross-AZ microservice traffic, use topology-aware routing (Kubernetes TopologySpreadConstraints) to prefer same-AZ communication. Avoid cross-region data movement unless the business requirement justifies the cost. Query large datasets in-place (Athena, BigQuery) rather than exporting them. → `engineering-knowledge-repository/network-egress-costs.md`

## Related Entries
- [Cloud Cost Optimization](cloud-cost-optimization.md) — network egress is a key component of cloud cost optimization
- [FinOps](finops.md) — egress costs must be attributed per service within the FinOps cost framework
- [CDN Pattern](cdn-pattern.md) — CDNs are the primary mitigation for internet egress costs on public-facing assets
- [Kubernetes](kubernetes.md) — topology-aware routing in Kubernetes reduces cross-AZ egress charges
- [Database Cost Optimization](database-cost-optimization.md) — cross-AZ database traffic and data transfer are components of database egress cost

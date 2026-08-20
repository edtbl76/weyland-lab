---
id: vpc-and-networking
tags: [pattern, infrastructure, security, cloud]
surfaces-at: [infrastructure-design]
related: [infrastructure-as-code, security-hardening, load-balancing, secrets-management, zero-trust-networking]
complexity: intermediate
---

# VPC and Cloud Networking

## What It Is
The foundational network architecture layer of cloud deployments — Virtual Private Clouds (VPCs), subnets, routing, and security controls that isolate and protect cloud resources. Every AWS, GCP, or Azure deployment lives within a VPC. Network design determines what can talk to what, what is exposed to the internet, and how traffic flows between services, databases, and external systems. Poor VPC design is a security risk (over-exposed resources) and an operational problem (misconfigured routing breaks deployments).

## When to Apply
- Every cloud infrastructure deployment (VPC design is a prerequisite, not optional)
- Before deploying databases, internal services, or any resource that should not be internet-accessible
- When designing multi-tier architectures (frontend, application, data layers)
- When establishing network security boundaries for compliance requirements

## Key Concepts
- **VPC (Virtual Private Cloud)**: A logically isolated network within a cloud provider. Resources deployed into a VPC are private by default. Each VPC has a CIDR block (e.g., `10.0.0.0/16`) defining its IP address range
- **Subnets**:
  - *Public subnet*: Has a route to the internet via an Internet Gateway. Resources here can receive inbound traffic from the internet. Use for: load balancers, NAT gateways, bastion hosts
  - *Private subnet*: No direct internet route. Resources here are not reachable from the internet. Use for: application servers, databases, internal services
  - Distribute subnets across multiple Availability Zones for high availability
- **Internet Gateway (IGW)**: Attaches to a VPC and enables internet connectivity for resources in public subnets. Required for any internet-facing resource
- **NAT Gateway**: Allows resources in private subnets to initiate outbound internet connections (for pulling packages, calling external APIs) without accepting inbound connections. Deployed in a public subnet; private subnet routes internet-bound traffic through it. Cost: charged per hour + per GB
- **Security Groups**: Stateful virtual firewalls attached to individual resources (EC2, RDS, Lambda VPC). Define allowed inbound and outbound traffic by protocol, port, and source/destination (CIDR or other security group). Default: deny all inbound, allow all outbound. Best practice: least privilege — allow only required ports from required sources
- **Network ACLs (NACLs)**: Stateless subnet-level firewall. Applied to all traffic entering/leaving a subnet. Useful for additional coarse-grained network controls (block specific IPs). Because stateless, must explicitly allow both inbound and outbound for each connection
- **Route Tables**: Define where traffic is routed within a VPC. Each subnet is associated with a route table. `0.0.0.0/0` → Internet Gateway routes internet-bound traffic; `0.0.0.0/0` → NAT Gateway for private subnets
- **VPC Peering / AWS Transit Gateway**: Connect multiple VPCs or multiple AWS accounts. VPC peering: direct 1:1 connection. Transit Gateway: hub-and-spoke for connecting many VPCs and on-premises networks. Required for multi-account architectures
- **VPC Endpoints**: Connect VPCs directly to AWS services (S3, DynamoDB, Secrets Manager) without traffic leaving AWS's private network. Eliminates the need for internet access to reach AWS services. Interface Endpoints (PrivateLink) and Gateway Endpoints
- **DNS within VPCs**: Route 53 Private Hosted Zones provide DNS resolution within VPCs. Use private DNS names for internal services instead of hardcoded private IPs
- **Typical Three-Tier Architecture**:
  - Public subnets (2+ AZs): Load balancers only
  - Private application subnets (2+ AZs): Application servers, ECS tasks
  - Private data subnets (2+ AZs): RDS, ElastiCache, databases
  - Security groups allow: LB → app (port 443/80), app → data (port 5432/6379 only), app → internet via NAT (port 443 only)

## In Practice
Method deploys all cloud infrastructure into multi-AZ VPCs with public/private subnet separation. Load balancers live in public subnets; application services and databases in private subnets. Security groups follow least privilege. NAT Gateways provide outbound internet for private subnets. VPC Endpoints for S3 and Secrets Manager eliminate unnecessary NAT Gateway charges. Infrastructure is defined in Terraform with consistent CIDR block conventions across environments.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — VPC and Cloud Networking**: The default rule is: databases and application servers go in private subnets, load balancers go in public subnets. Never put a database in a public subnet. Security groups are your primary network access control — apply least privilege: only open the ports that specific sources need. NAT Gateways are expensive ($0.045/hour + egress) — use VPC Endpoints for AWS services to eliminate unnecessary NAT traffic. Spread across 2+ Availability Zones from day one — retrofitting multi-AZ into a single-AZ design is painful. Define VPC CIDR ranges with enough headroom — changing them later requires full infrastructure migration. → `engineering-knowledge-repository/vpc-and-networking.md`

## Related Entries
- [Infrastructure as Code](infrastructure-as-code.md) — VPC architecture is defined and managed via Terraform or CDK
- [Security Hardening](security-hardening.md) — VPC design is a core layer of cloud security hardening
- [Load Balancing](load-balancing.md) — load balancers sit in public subnets; backend instances in private subnets
- [Secrets Management](secrets-management.md) — VPC Endpoints allow private subnet access to Secrets Manager without internet routing
- [Zero-Trust Networking](zero-trust-networking.md) — zero-trust principles extend beyond VPC perimeter controls to application-level authentication

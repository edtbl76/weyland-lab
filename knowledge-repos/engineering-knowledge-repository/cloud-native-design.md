---
id: cloud-native-design
tags: [principle, cloud, infrastructure]
surfaces-at: [nfr-requirements, infrastructure-design, application-design]
related: [twelve-factor-app, container-orchestration, infrastructure-as-code, auto-scaling]
complexity: intermediate
---

# Cloud-Native Design

## What It Is
An approach to building and running applications that exploits the advantages of cloud computing — elastic scaling, managed services, self-healing infrastructure, and pay-per-use economics. Cloud-native applications are designed from the ground up for cloud environments: containerized, dynamically orchestrated, microservices-based, observable, and resilient to infrastructure failure. The CNCF (Cloud Native Computing Foundation) governs the ecosystem.

## When to Apply
- Greenfield cloud deployments — design for cloud-native from day one
- When migrating from on-premises to cloud — cloud-native replatforming extracts the full value of cloud investment
- Systems requiring elastic scaling, high availability, and operational efficiency
- When leveraging managed services (RDS, SQS, S3) instead of self-managing infrastructure

## When Not to Apply
- Lift-and-shift migrations where the goal is only to move infrastructure, not redesign applications — don't force cloud-native patterns on applications not architected for them
- Very simple applications where cloud-native overhead (Kubernetes, service mesh, etc.) isn't justified

## Key Concepts
- **Containers**: The unit of deployment — Docker images are immutable, portable, and platform-independent
- **Orchestration**: Kubernetes manages container scheduling, scaling, health checks, and networking
- **Microservices**: Cloud-native applications decompose along business capabilities for independent deployability and scaling
- **Managed Services**: Use cloud provider services (RDS, ElastiCache, SQS) instead of self-managing databases, caches, and queues — offload operational complexity
- **Observability**: Cloud-native systems require built-in observability — distributed tracing, structured logging, metrics, and health endpoints
- **Elasticity**: Scale in and out automatically in response to demand — auto-scaling groups, Kubernetes HPA
- **Infrastructure as Code**: All cloud infrastructure defined and managed through code
- **Twelve-Factor Principles**: The twelve-factor app methodology is the application-level companion to cloud-native infrastructure design

## In Practice
Cloud-native design is the default approach for Method cloud engagements. The CNCF landscape provides the standard tooling: Kubernetes (orchestration), Prometheus/Grafana (observability), Helm (packaging), Argo CD (deployment). Design decisions: managed services vs. self-hosted, service mesh vs. application-level resilience, monorepo vs. polyrepo for Kubernetes manifests.

## Engineering Knowledge
💡 **Engineering Knowledge — Cloud-Native Design**: Build for cloud advantages from day one: containers, managed services, auto-scaling, and infrastructure as code. Don't lift-and-shift a VM-based architecture into Kubernetes — the operational complexity without the design benefits isn't worthwhile. Use managed services (RDS over self-managed Postgres, SQS over self-managed RabbitMQ) — let the cloud provider handle the undifferentiated heavy lifting. Pair with twelve-factor principles for application-level cloud-native design. → `engineering-knowledge-repository/cloud-patterns/cloud-native-design.md`

## Related Entries
- [Twelve-Factor App](../architectural-philosophy/twelve-factor-app.md) — application-level cloud-native design principles
- [Container Orchestration](container-orchestration.md) — Kubernetes is the standard cloud-native orchestration layer
- [Infrastructure as Code](../deployment/infrastructure-as-code.md) — IaC is a prerequisite for cloud-native operations

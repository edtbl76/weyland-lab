---
id: container-orchestration
tags: [tooling, infrastructure, cloud, deployment]
surfaces-at: [infrastructure-design, nfr-requirements]
related: [cloud-native-design, auto-scaling, gitops, immutable-infrastructure, service-mesh]
complexity: intermediate
---

# Container Orchestration

## What It Is
The automated management of containerized workloads — scheduling, scaling, networking, health monitoring, and self-healing. Kubernetes is the de facto industry standard for container orchestration. It abstracts infrastructure, handles container placement across nodes, restarts failed containers, manages rolling deployments, and provides service discovery and load balancing. Managed Kubernetes services (EKS, GKE, AKS) reduce operational overhead by handling control plane management.

## When to Apply
- Any production containerized workload beyond a single container
- Systems requiring high availability, automatic failover, and rolling deployments
- Microservices architectures where independent scaling of services is required
- Teams running multiple applications that benefit from shared infrastructure

## When Not to Apply
- Single-container applications or simple services — Docker Compose + a VM may be sufficient
- Very small teams without Kubernetes expertise — managed alternatives (AWS ECS, Heroku, Railway) reduce operational complexity
- Serverless workloads — Kubernetes is unnecessary when the cloud provider handles all scheduling

## Key Concepts
- **Pod**: The smallest deployable unit — one or more containers sharing network and storage
- **Deployment**: Manages a set of replica Pods — handles rolling updates, rollbacks, and desired state
- **Service**: Provides a stable network endpoint and load balancing for a set of Pods — Pods come and go; Services provide stable DNS
- **Namespace**: Logical cluster partitioning — separate namespaces for prod, staging, dev
- **ConfigMap / Secret**: Kubernetes-native configuration and secrets storage — injected into Pods at runtime
- **Helm**: The Kubernetes package manager — charts package related Kubernetes resources into deployable units
- **Operators**: Custom controllers that extend Kubernetes to manage stateful applications (databases, Kafka clusters)
- **Liveness / Readiness Probes**: Health checks that Kubernetes uses to determine whether to route traffic to a Pod and whether to restart it

## In Practice
Kubernetes (EKS/GKE/AKS) is Method's standard container orchestration platform for production workloads. Helm charts package all service manifests. Argo CD handles GitOps-based deployment. The key operational competencies: RBAC configuration, resource limits/requests, probe configuration, and horizontal pod autoscaling.

## Engineering Knowledge
💡 **Engineering Knowledge — Container Orchestration (Kubernetes)**: Kubernetes is the standard — Pods, Deployments, Services, ConfigMaps. Use managed Kubernetes (EKS/GKE/AKS) unless you have a reason to run your own control plane. Package with Helm, deploy with Argo CD (GitOps). Configure liveness and readiness probes — without them, Kubernetes routes traffic to Pods that aren't ready. Set resource requests and limits on every container — without requests, Kubernetes can't schedule correctly; without limits, a runaway container starves its neighbors. → `engineering-knowledge-repository/cloud-patterns/container-orchestration.md`

## Related Entries
- [Cloud-Native Design](cloud-native-design.md) — container orchestration is the infrastructure layer of cloud-native design
- [Auto-Scaling](auto-scaling.md) — Kubernetes HPA automates scaling within the orchestration layer
- [GitOps](../deployment/gitops.md) — GitOps manages Kubernetes deployments declaratively via Git
- [Service Mesh](../architectural-styles/service-mesh.md) — service mesh runs on top of Kubernetes orchestration

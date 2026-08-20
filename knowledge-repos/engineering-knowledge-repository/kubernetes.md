---
id: kubernetes
tags: [tooling, infrastructure, deployment, backend]
surfaces-at: [infrastructure-design, application-design]
related: [containers, auto-scaling, spot-instances, service-mesh, infrastructure-as-code, horizontal-vs-vertical-scaling]
complexity: intermediate
---

# Kubernetes

## What It Is
An open-source container orchestration platform that automates the deployment, scaling, and operation of containerized applications. Kubernetes abstracts the underlying infrastructure — applications declare their desired state (how many replicas, resource requirements, health checks) and Kubernetes continuously reconciles actual state to match. It is the de facto standard for running containers in production at scale, supported natively by all major cloud providers (EKS, GKE, AKS).

## When to Apply
- Running containerized applications that need automated scaling, self-healing, and rolling deployments
- Multiple services requiring consistent deployment and operational patterns
- Workloads that need fine-grained resource allocation and isolation
- When the operational overhead of Kubernetes is justified by scale and complexity

## Key Concepts
- **Pod**: The smallest deployable unit — one or more containers sharing network and storage. Containers in a pod communicate via localhost. Most workloads use one container per pod
- **Deployment**: Declares the desired state for a set of pods — replica count, container image, resource limits, update strategy. Kubernetes reconciles to maintain the desired replica count; automatically replaces failed pods
- **Service**: A stable network endpoint for a set of pods. Pods are ephemeral with changing IPs; a Service provides a consistent DNS name and load balances across healthy pod replicas
- **Namespace**: Logical isolation within a cluster — separate environments (dev/staging/prod), teams, or applications. Resource quotas and RBAC are applied per namespace
- **Resource Requests and Limits**: Request — guaranteed resources; the scheduler uses this to place pods. Limit — maximum resources; the pod is throttled (CPU) or OOM-killed (memory) if exceeded. Always set both; pods without requests are unpredictably scheduled
- **Horizontal Pod Autoscaler (HPA)**: Automatically scales pod replica count based on CPU, memory, or custom metrics. Complements cluster autoscaling (adding/removing nodes) for full elasticity
- **ConfigMaps and Secrets**: Externalize configuration from container images. ConfigMaps for non-sensitive config; Secrets for credentials (integrate with Vault or AWS Secrets Manager for production secret management)
- **Ingress**: HTTP/HTTPS routing from outside the cluster to services. Ingress controllers (nginx, AWS ALB Ingress Controller) handle TLS termination, path-based routing, and host-based routing
- **Node Pools**: Groups of nodes with specific instance types. Use separate node pools for different workload types — general workloads, GPU workloads, spot instances. Taints and tolerations control which pods schedule on which pools
- **Managed Kubernetes**: EKS (AWS), GKE (GCP), AKS (Azure) manage the control plane. Reduces operational burden significantly — use managed over self-hosted unless there is a specific reason not to

## In Practice
Method uses EKS for Kubernetes deployments. Workloads are deployed via Helm charts with ArgoCD for GitOps continuous delivery. Separate node pools for general workloads and spot instances. HPA scales on CPU and custom application metrics. Resource requests and limits are required on all deployments. Secrets are managed via AWS Secrets Manager with the External Secrets Operator.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Kubernetes**: Always set resource requests and limits — pods without them are scheduled unpredictably and can starve other workloads. Use HPA for application-level autoscaling and Cluster Autoscaler for node-level elasticity. Separate workloads across node pools by type (general, spot, GPU) using taints and tolerations. Use managed Kubernetes (EKS/GKE/AKS) — running your own control plane is significant operational overhead with no benefit for most teams. Integrate Secrets with a secrets manager (Vault, AWS Secrets Manager) rather than storing credentials in Kubernetes Secrets directly. GitOps (ArgoCD, Flux) is the standard for managing Kubernetes deployments at scale. → `engineering-knowledge-repository/kubernetes.md`

## Related Entries
- [Containers](containers.md) — Kubernetes orchestrates containers; understanding containers is prerequisite to Kubernetes
- [Auto Scaling](auto-scaling.md) — HPA and Cluster Autoscaler implement Kubernetes-native auto scaling
- [Spot Instances](spot-instances.md) — spot node pools in Kubernetes reduce compute costs for interruption-tolerant workloads
- [Service Mesh](service-mesh.md) — service meshes (Istio, Linkerd) add observability and traffic management to Kubernetes services
- [Infrastructure as Code](infrastructure-as-code.md) — Kubernetes manifests and Helm charts are infrastructure as code
- [Horizontal vs. Vertical Scaling](horizontal-vs-vertical-scaling.md) — Kubernetes HPA implements horizontal scaling for containerized workloads

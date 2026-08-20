---
id: service-discovery
tags: [pattern, infrastructure, microservices, network]
surfaces-at: [infrastructure-design, application-design]
related: [microservices, api-gateway-pattern, container-orchestration, service-mesh]
complexity: intermediate
---

# Service Discovery

## What It Is
The mechanism by which services in a distributed system locate each other dynamically, without hardcoded IP addresses or hostnames. In dynamic environments (Kubernetes, cloud VMs with auto-scaling), service instances start and stop constantly — their IP addresses change. Service discovery maintains a registry of healthy instances and provides mechanisms for services to find each other by name.

## When to Apply
- Microservices architectures where services need to call each other
- Auto-scaling environments where instance IP addresses are ephemeral
- Any system where hardcoding service endpoints would create operational fragility

## When Not to Apply
- Monolithic single-service applications with no inter-service calls
- Very simple two-service setups where static configuration is manageable

## Key Concepts
- **Client-Side Discovery**: The client queries the service registry and load-balances across available instances itself (Netflix Eureka pattern)
- **Server-Side Discovery**: A load balancer or router queries the registry and routes to available instances — the client doesn't know about discovery (AWS ELB, Kubernetes Services)
- **Service Registry**: The store of available service instances — health status, addresses, ports (Consul, Eureka, Kubernetes etcd)
- **DNS-Based Discovery**: The simplest form — DNS resolves service names to instance addresses. Kubernetes Services use this model: `http://payment-service:8080` resolves to the ClusterIP Service.
- **Health Checks**: The registry removes instances that fail health checks — ensures discovery returns only healthy endpoints
- **Kubernetes Service**: The built-in service discovery mechanism — Services provide a stable ClusterIP and DNS name; Kubernetes kube-proxy load balances across Pods

## In Practice
Kubernetes Services provide service discovery natively in Method Kubernetes engagements — no external service registry needed. Services communicate by DNS name (e.g., `http://payment-service.default.svc.cluster.local`). For multi-cluster or multi-cloud service discovery, Consul or AWS Cloud Map provides the cross-cluster registry.

## Engineering Knowledge
💡 **Engineering Knowledge — Service Discovery**: In dynamic environments, you can't hardcode IPs. Services find each other by name through a registry. In Kubernetes, this is built-in: Services get a stable DNS name; call `http://payment-service:8080` and Kubernetes resolves and load-balances automatically. No additional service registry needed for single-cluster deployments. For cross-cluster or multi-cloud discovery, use Consul or AWS Cloud Map. → `engineering-knowledge-repository/cloud-patterns/service-discovery.md`

## Related Entries
- [Microservices](../architectural-styles/microservices.md) — service discovery is essential infrastructure for microservices
- [Container Orchestration](container-orchestration.md) — Kubernetes provides built-in service discovery
- [API Gateway Pattern](../architectural-styles/api-gateway-pattern.md) — the API gateway performs external service discovery for inbound traffic

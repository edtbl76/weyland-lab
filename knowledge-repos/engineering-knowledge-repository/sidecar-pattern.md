---
id: sidecar-pattern
tags: [pattern, infrastructure, microservices]
surfaces-at: [infrastructure-design, nfr-design]
related: [service-mesh, ambassador-pattern, microservices, twelve-factor-app]
complexity: intermediate
---

# Sidecar Pattern

## What It Is
A deployment pattern where a helper container is deployed alongside the main application container, sharing its lifecycle, network, and storage. The sidecar handles cross-cutting concerns (logging, monitoring, proxying, configuration, security) so the main container doesn't have to. Named after the sidecar attached to a motorcycle — the main container drives; the sidecar provides support.

## When to Apply
- Injecting cross-cutting concerns into services without modifying application code — especially useful in polyglot architectures where the same concern must be applied to services in multiple languages
- Service Mesh: deploying a proxy sidecar (Envoy) to handle service-to-service communication
- Centralizing log collection — a logging agent sidecar ships logs from the app container to a central aggregator
- Monitoring agents, secrets injection, configuration refresh

## When Not to Apply
- When the concern can be addressed via a shared library — sidecars add deployment complexity; a library is simpler for single-language stacks
- Very small services where the operational overhead of multiple containers outweighs the benefits
- When the sidecar introduces unacceptable latency in the request path

## Key Concepts
- **Co-Deployment**: Sidecar and main container share the same Pod (Kubernetes), same lifecycle, and network namespace
- **Shared Network**: The sidecar and main container communicate via `localhost` — no network hop
- **Transparent Proxy**: In service mesh, the sidecar proxy transparently intercepts all inbound/outbound traffic without the application knowing
- **Language Agnostic**: The same sidecar logic applies to services in any language — no need to reimplement the concern per language
- **Pod (Kubernetes)**: The Kubernetes Pod is the unit of co-deployment for sidecars — all containers in a Pod share network and can share volumes

## In Practice
The Sidecar pattern is the enabler of Service Mesh — Istio/Linkerd inject Envoy sidecar proxies automatically into every Pod. In Method engagements, sidecars are also used for: log agents (Filebeat sidecar shipping to Elasticsearch), secrets refresh agents (Vault Agent sidecar), and Prometheus exporters for application metrics.

## Engineering Knowledge
💡 **Engineering Knowledge — Sidecar Pattern**: Deploy cross-cutting concerns in a helper container alongside your service — the sidecar handles log shipping, metrics collection, secret injection, or proxying without any changes to the application. Service mesh (Istio, Linkerd) auto-injects Envoy as a sidecar to every pod transparently. The sidecar and main container share `localhost` — no network overhead. Language-agnostic: same sidecar logic works for Node, Java, and Go services equally. → `engineering-knowledge-repository/infrastructure/sidecar-pattern.md`

## Related Entries
- [Service Mesh](../architectural-styles/service-mesh.md) — service mesh is the large-scale deployment of sidecar proxies
- [Ambassador Pattern](ambassador-pattern.md) — the ambassador is a specialized sidecar for outbound network concerns
- [Twelve-Factor App](../architectural-philosophy/twelve-factor-app.md) — the twelve-factor log principle (stdout) is what makes sidecar log agents possible

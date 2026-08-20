---
id: zero-trust-networking
tags: [pattern, security, infrastructure]
surfaces-at: [infrastructure-design, application-design]
related: [vpc-and-networking, security-hardening, secrets-management, service-mesh]
complexity: advanced
---

# Zero-Trust Networking

## What It Is
A security model that eliminates the assumption that anything inside the network perimeter is trustworthy. Traditional network security assumes that internal traffic (within a VPC or data center) is safe and only external traffic needs inspection. Zero-trust replaces this with: "never trust, always verify" — every request, regardless of source, must authenticate, be authorized, and be encrypted. Zero-trust is a response to the reality that perimeter-based security fails when insiders are compromised, credentials are stolen, or attackers move laterally once inside the network.

## When to Apply
- Organizations moving away from VPN-based remote access
- Multi-cloud or hybrid cloud environments where "inside the network" is ambiguous
- Applications with strong compliance requirements (FedRAMP, PCI, HIPAA, SOC 2)
- Microservices architectures where service-to-service trust is explicit, not assumed
- When insider threats or credential theft are in the threat model

## Key Concepts
- **Core Principles**:
  1. *Verify explicitly*: Always authenticate and authorize based on all available data — identity, location, device state, service
  2. *Use least privilege access*: Limit access to the minimum needed, time-bound where possible
  3. *Assume breach*: Design assuming the attacker is already inside — minimize blast radius, segment access, detect lateral movement
- **Identity-Based Access**: Network location is not a trust signal. Every user, service, and device must authenticate with a verifiable identity. mTLS (mutual TLS) for service-to-service; OIDC/SAML for user access; IAM roles for cloud service identity
- **mTLS (Mutual TLS)**: Both parties in a service-to-service connection present certificates and verify each other's identity. Eliminates network-level trust — a compromised service cannot impersonate another service without its certificate. Service meshes (Istio, Linkerd) implement mTLS transparently between services
- **Micro-Segmentation**: Instead of one flat internal network, services can only communicate with explicitly permitted peers. Security groups and network policies enforce this at the infrastructure level. A compromised service cannot reach arbitrary internal services — only its declared dependencies
- **Service Identity**: In Kubernetes, SPIFFE/SPIRE provides workload identity certificates (SVIDs) to pods. Services use their SVID to authenticate to other services and to external secrets stores. AWS IAM Roles for Service Accounts (IRSA) provides AWS-native workload identity
- **Zero Trust Access (User-Facing)**: Replace VPN with identity-aware proxies (Cloudflare Access, Google BeyondCorp Enterprise, Zscaler). Users authenticate to access internal applications; access is granted per-application, not per-network. No VPN tunnel needed; works from any device location
- **Continuous Verification**: Traditional sessions trust once and persist indefinitely. Zero-trust requires continuous verification — short-lived tokens, regular re-authentication, session risk scoring based on device posture and behavior
- **Encryption in Transit**: All internal service-to-service communication is encrypted, even within the VPC. Internal traffic is not exempt from TLS. Service meshes automate this at the infrastructure layer
- **Audit Everything**: Zero-trust requires comprehensive audit logs of all authentication and authorization decisions. Who accessed what, when, from where, and with what outcome. Required for breach detection and forensics

## In Practice
Method uses security groups for micro-segmentation within VPCs — services only have inbound rules from their direct callers. Service meshes (Istio) provide mTLS between microservices on Kubernetes. IRSA provides workload identity for AWS API access. Cloudflare Access gates internal tooling (Grafana, internal APIs) without a VPN. Short-lived credentials via IAM roles replace long-lived access keys. All API calls are logged to CloudTrail.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Zero-Trust Networking**: Being inside a VPC does not mean you're safe — assume lateral movement is possible and design micro-segmentation accordingly. mTLS between services is the zero-trust primitive for microservices: it authenticates both parties before any data flows. Service meshes (Istio, Linkerd) implement mTLS transparently — enabling zero-trust service identity without changing application code. Replace VPN-based internal access with identity-aware proxies (Cloudflare Access) — per-application authorization is more precise than network-level access, and it works from anywhere. Never use long-lived credentials where short-lived role-based credentials are possible. → `engineering-knowledge-repository/zero-trust-networking.md`

## Related Entries
- [VPC and Networking](vpc-and-networking.md) — VPC network controls are the perimeter layer; zero-trust extends security inward
- [Security Hardening](security-hardening.md) — zero-trust is an advanced application of security hardening principles
- [Secrets Management](secrets-management.md) — zero-trust requires strong credential management and short-lived tokens
- [Service Mesh](service-mesh.md) — service meshes implement mTLS and traffic policies for zero-trust service-to-service communication

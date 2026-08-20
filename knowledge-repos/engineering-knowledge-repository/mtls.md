---
id: mtls
tags: [protocol, security, network, distributed-systems]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [zero-trust-security, service-mesh, oauth2-oidc, api-security]
complexity: intermediate
---

# Mutual TLS (mTLS)

## What It Is
An extension of TLS (Transport Layer Security) where both the client and the server authenticate each other using certificates. Standard TLS authenticates only the server (the client verifies the server's certificate). Mutual TLS adds client authentication — the server also verifies a certificate presented by the client. This enables cryptographic, identity-based authentication for service-to-service communication without passwords or API keys.

## When to Apply
- Service-to-service communication in Zero Trust architectures — mTLS is the standard mechanism for service identity
- When services need to prove their identity to each other, not just to users
- Service mesh implementations (Istio, Linkerd) transparently enforce mTLS for all service-to-service calls
- APIs where client identity must be cryptographically verified (financial APIs, healthcare integrations)

## When Not to Apply
- Browser-to-API communication — client certificate distribution to end users is impractical (OAuth2 is the correct mechanism here)
- Environments without certificate lifecycle management infrastructure — unmanaged certificates expire and cause outages

## Key Concepts
- **Server Certificate**: The server presents its certificate — standard TLS, proves the server's identity to the client
- **Client Certificate**: The client also presents a certificate — the additional step in mTLS, proves the client's identity to the server
- **Certificate Authority (CA)**: Issues and signs certificates — the trust anchor. In service meshes, the control plane acts as an internal CA.
- **Certificate Rotation**: Certificates expire — mTLS infrastructure must automatically rotate certificates before expiry. Service meshes handle this automatically.
- **SPIFFE / SPIRE**: Standards for service identity in cloud-native systems — each service gets a cryptographic identity (SPIFFE ID) that mTLS can use
- **Transparent Enforcement**: Service meshes (Istio, Linkerd) inject sidecars that enforce mTLS transparently — services don't need to handle certificate management themselves

## In Practice
mTLS is Method's standard for service-to-service authentication in microservices deployments with a service mesh. Istio/Linkerd enforce it transparently — the application never handles certificates. For environments without a service mesh, AWS App Mesh or standalone Envoy proxies can enforce mTLS at the infrastructure level.

## Engineering Knowledge
💡 **Engineering Knowledge — Mutual TLS (mTLS)**: In Zero Trust service-to-service communication, both sides prove their identity with certificates. Standard TLS proves only the server's identity; mTLS adds client authentication. Service meshes (Istio, Linkerd) enforce mTLS transparently between all services — no application-level certificate handling. mTLS provides stronger identity guarantees than API keys or network-level trust. The operational challenge is certificate lifecycle management — service meshes automate rotation. → `engineering-knowledge-repository/security/mtls.md`

## Related Entries
- [Zero Trust Security](zero-trust-security.md) — mTLS is the service-to-service authentication mechanism in Zero Trust architectures
- [Service Mesh](../architectural-styles/service-mesh.md) — service mesh sidecars enforce mTLS transparently
- [OAuth2/OIDC](oauth2-oidc.md) — OAuth2 for user authentication; mTLS for service authentication

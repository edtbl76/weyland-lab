---
id: zero-trust-security
tags: [principle, security, distributed-systems, network]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [principle-of-least-privilege, mtls, oauth2-oidc, rbac, defense-in-depth]
complexity: intermediate
---

# Zero Trust Security

## What It Is
A security model based on the principle "never trust, always verify." Traditional security assumed anything inside the network perimeter was trustworthy — Zero Trust eliminates the concept of a trusted network zone. Every request — regardless of origin (internal or external) — must be authenticated, authorized, and validated. Access is granted per-request based on identity, device state, and context, not network location.

## When to Apply
- Cloud and hybrid environments where the network perimeter is dissolved
- When employees access corporate systems from personal devices and home networks
- Microservices architectures where service-to-service calls traverse internal networks
- Systems with sensitive data where insider threats or lateral movement post-compromise is a concern
- Any new system design — Zero Trust is the modern security baseline, not an advanced option

## When Not to Apply
- Isolated, air-gapped systems with genuinely trusted physical perimeters
- Very simple internal tools where the cost of Zero Trust implementation exceeds the risk

## Key Concepts
- **Identity is the New Perimeter**: Authentication and authorization are required for every access, regardless of network location
- **Least Privilege**: Users and services get only the minimum access required — no broad access grants
- **Microsegmentation**: Network divided into small segments with strict access controls between them — limits lateral movement
- **Device Posture**: Access decisions consider device health (patched OS, MDM enrolled, disk encrypted) not just user identity
- **Continuous Verification**: Access is re-verified continuously, not granted once and assumed valid — short-lived tokens, step-up authentication for sensitive operations
- **Assume Breach**: Design assuming attackers are already inside — minimize blast radius through segmentation and least privilege
- **mTLS**: Service-to-service authentication using mutual TLS is a key Zero Trust mechanism in microservices

## In Practice
Zero Trust is the security posture Method recommends for all new production systems. For cloud infrastructure: enforce mTLS between services (service mesh), use short-lived credentials from a secrets manager (no static API keys), enforce IAM least privilege, and segment networks. For user access: require MFA, enforce device posture, use identity-aware proxies (BeyondCorp model).

## Engineering Knowledge
💡 **Engineering Knowledge — Zero Trust Security**: Never trust, always verify — even internal traffic. Every request must authenticate and authorize, regardless of where it comes from. For services: mTLS between all service calls, short-lived credentials, no hardcoded keys. For users: MFA, device posture checks, identity-aware access. The key shift: stop trusting the network, start trusting verified identities. Design assuming breach: limit lateral movement through segmentation and least privilege. → `engineering-knowledge-repository/security/zero-trust-security.md`

## Related Entries
- [Principle of Least Privilege](principle-of-least-privilege.md) — core operating principle of Zero Trust
- [mTLS](mtls.md) — mutual TLS implements Zero Trust service-to-service authentication
- [OAuth2/OIDC](oauth2-oidc.md) — identity verification layer for user and service access
- [Defense in Depth](defense-in-depth.md) — Zero Trust is a component of defense-in-depth strategy

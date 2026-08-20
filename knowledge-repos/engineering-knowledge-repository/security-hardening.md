---
id: security-hardening
tags: [principle, security, infrastructure, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [containers, principle-of-least-privilege, zero-trust-security, defense-in-depth, threat-modeling, injection-attacks]
complexity: intermediate
---

# Security Hardening

## What It Is
The process of reducing a system's attack surface by eliminating unnecessary components, tightening configurations, and applying security controls systematically. Hardening addresses the gap between a default installation (often permissive for ease of use) and a production-secure configuration. It applies at every layer: container images, operating systems, cloud configurations, network rules, application frameworks, and database access. The principle: anything not explicitly required should be disabled or removed.

## When to Apply
- Before deploying any system to production
- As part of infrastructure provisioning — hardening is far easier to implement upfront than retrofit
- After a security review or penetration test identifies configuration weaknesses
- When onboarding new infrastructure components

## Key Concepts
- **Attack Surface Reduction**: Remove or disable everything not required — unused packages, open ports, default accounts, sample applications, unnecessary services. Every enabled component is a potential vulnerability
- **Principle of Least Privilege**: Every process, service, and user gets the minimum permissions required to function. Database service accounts can read/write their database only. Application roles cannot drop tables. See Principle of Least Privilege entry
- **Container Hardening**: Use minimal base images (distroless, alpine). Run as non-root user. Set filesystem as read-only where possible. Drop all Linux capabilities; add back only what's needed. Scan images for known CVEs before deployment
- **OS Hardening**: Disable unused services and daemons. Apply all security patches. Configure firewalls to deny by default. Use SSH key authentication; disable password auth. Audit cron jobs and startup scripts
- **Network Hardening**: Security groups / firewall rules default deny. Only open ports that are required. Segregate networks — database tier should not be accessible from the internet. Use VPC endpoints for AWS service access
- **Default Credentials**: Rotate or disable all default passwords immediately. Never deploy with default database passwords, admin credentials, or API keys. Automate credential rotation
- **Cloud Security Posture**: Enable cloud provider security baselines — AWS Security Hub, GCP Security Command Center. Run CIS benchmark checks. Enable CloudTrail / audit logging for all API calls. Enforce MFA on cloud console access
- **Secrets Management**: Never hardcode secrets in code, container images, or config files. Use a secrets manager (AWS Secrets Manager, HashiCorp Vault). Rotate secrets regularly
- **Dependency Scanning**: Regularly scan application dependencies for known CVEs — Dependabot, Snyk, OWASP Dependency-Check. Update vulnerable dependencies promptly
- **Security Benchmarks**: CIS (Center for Internet Security) benchmarks provide hardening checklists for OS, cloud services, Kubernetes, and databases. STIG (Security Technical Implementation Guide) for government/compliance contexts

## In Practice
Method uses hardened container base images (distroless or alpine), runs all containers as non-root, and enforces read-only filesystems where possible. Security groups follow default-deny. Secrets are managed via AWS Secrets Manager. Dependabot runs on all repositories. AWS Security Hub provides continuous posture monitoring.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Security Hardening**: Default configurations are optimized for convenience, not security — harden before production. Run containers as non-root with read-only filesystems and minimal capabilities. Apply principle of least privilege to every IAM role, service account, and database user. Default-deny all network rules and open only what's required. Rotate default credentials immediately; manage secrets through a secrets manager. Scan container images and dependencies for CVEs in CI — don't discover vulnerabilities in production. Use CIS benchmarks as your hardening checklist — they cover OS, cloud, and Kubernetes configurations comprehensively. → `engineering-knowledge-repository/security-hardening.md`

## Related Entries
- [Containers](containers.md) — container hardening is a primary application of security hardening principles
- [Principle of Least Privilege](principle-of-least-privilege.md) — least privilege is the foundational principle underlying hardening decisions
- [Zero Trust Security](zero-trust-security.md) — zero trust extends hardening principles to network and identity architecture
- [Defense in Depth](defense-in-depth.md) — hardening is one layer within a defense-in-depth security strategy
- [Threat Modeling](threat-modeling.md) — threat modeling identifies what to harden and in what priority order
- [Injection Attacks](injection-attacks.md) — application-layer hardening prevents injection attack vectors

---
id: encryption
tags: [pattern, security, infrastructure, backend]
surfaces-at: [infrastructure-design, application-design]
related: [secrets-management, vpc-and-networking, data-privacy, security-hardening, zero-trust-networking]
complexity: intermediate
---

# Encryption

## What It Is
The cryptographic transformation of data to render it unreadable without the appropriate key — protecting data in transit (between systems over a network) and at rest (stored in databases, files, and backups). Encryption is the foundational data protection control: even if an attacker gains access to encrypted data, they cannot read it without the key. For engineering teams, encryption means configuring systems to use TLS for all data in transit and enabling encryption for all storage — and doing key management correctly so encryption is actually effective.

## When to Apply
- All data in transit (all network communication, without exception)
- All data at rest (databases, file storage, backups, logs)
- Any sensitive data (PII, credentials, financial data) requiring field-level protection beyond storage encryption
- Compliance requirements (PCI, HIPAA, GDPR, SOC 2) that mandate encryption

## Key Concepts
- **Encryption in Transit (TLS)**:
  - All HTTP traffic must use TLS (HTTPS). HTTP is not acceptable for any production traffic
  - TLS 1.2 minimum; TLS 1.3 preferred (faster handshake, stronger defaults)
  - Certificate management: AWS Certificate Manager (ACM) provides free, auto-renewed certificates. Let's Encrypt for non-AWS environments
  - Internal service-to-service traffic should also use TLS — being inside a VPC does not mean traffic is safe (see zero-trust principles)
  - mTLS (mutual TLS) authenticates both parties in a connection. Used for service-to-service communication in zero-trust architectures
- **Encryption at Rest**:
  - AWS storage services support encryption at rest: S3 (SSE-S3, SSE-KMS), RDS (at-rest encryption via KMS), EBS volumes, DynamoDB, SQS, SNS
  - Enable encryption at rest by default on all AWS resources. It's a checkbox — there is no reason not to
  - Encryption key management is the critical concern: who controls the keys?
- **Key Management Service (KMS)**:
  - AWS KMS manages cryptographic keys; services encrypt/decrypt via KMS API calls
  - KMS Customer Managed Keys (CMK): you control key rotation, access policies, and key deletion. Required for compliance in regulated industries
  - KMS-managed keys: AWS manages key rotation; simpler but less control
  - Key access is controlled via IAM policies — only services that need to decrypt a specific dataset should have `kms:Decrypt` permissions
- **Field-Level Encryption**: Encrypting specific columns or fields within a database, in addition to storage-level encryption. Use for: credit card numbers (tokenize via PCI-compliant service), SSNs, passwords (always hash, never encrypt). Provides protection even if the database is compromised while storage keys are not
- **Password Storage**: Passwords must be hashed (not encrypted) using purpose-built password hashing algorithms: Argon2id (recommended), bcrypt, scrypt. Never store plaintext passwords. Never use MD5 or SHA-256 alone for password hashing — they are too fast. Password hashers are deliberately slow to resist brute-force attacks
- **Envelope Encryption**: AWS KMS implements envelope encryption: a data key (DEK) encrypts the actual data; a master key (KEK) encrypts the data key. The encrypted data key is stored alongside the data. This pattern allows re-keying without re-encrypting all data
- **Certificate Pinning**: Embedding the expected certificate or public key in the client application, rejecting connections with unexpected certificates. Used in mobile applications to prevent man-in-the-middle attacks. Complex to maintain (certificate rotations break pinned clients)
- **Common Mistakes**:
  - Storing encryption keys next to encrypted data (negates encryption)
  - Using weak algorithms (MD5, SHA-1, DES, 3DES) — use AES-256-GCM, ChaCha20-Poly1305
  - Rolling your own cryptography — always use vetted libraries (libsodium, AWS Encryption SDK)
  - Disabling certificate validation (`verify=False`) in HTTP clients — common in development, catastrophic in production

## In Practice
Method enforces HTTPS-only on all services; HTTP is redirected to HTTPS at the load balancer. All AWS storage is encrypted at rest with KMS CMKs. Database column-level encryption via SQLAlchemy encrypted field types for PII columns (email, phone, address). Passwords are hashed with Argon2id via the `argon2-cffi` Python library. KMS key access is scoped per service via IAM roles — each service can only decrypt its own data. ACM manages all TLS certificates with auto-renewal.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Encryption**: Enable encryption at rest on every AWS storage resource — it's a single checkbox in Terraform and there is no performance penalty for most workloads. TLS everywhere, including internal service-to-service traffic — "it's internal" is not a security model. Manage encryption keys separately from the data they protect; KMS CMKs with per-service access policies are the right pattern. Never roll your own crypto; use AWS Encryption SDK or libsodium. Passwords are hashed (Argon2id), not encrypted — if you can decrypt a password, it's stored wrong. → `engineering-knowledge-repository/encryption.md`

## Related Entries
- [Secrets Management](secrets-management.md) — KMS keys are secrets that must be managed with the same rigor as application credentials
- [VPC and Networking](vpc-and-networking.md) — TLS secures data in transit even within the VPC
- [Data Privacy](data-privacy.md) — encryption is a primary technical control for personal data protection
- [Security Hardening](security-hardening.md) — encryption is a core layer of the defense-in-depth security hardening framework
- [Zero-Trust Networking](zero-trust-networking.md) — zero-trust requires encryption of all internal traffic, not just perimeter traffic

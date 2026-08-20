---
id: cryptography-fundamentals
tags: [reference, security, backend]
surfaces-at: [application-design]
related: [encryption, jwt, session-management, mtls, secrets-management]
complexity: intermediate
---

# Cryptography Fundamentals

## What It Is
The core cryptographic concepts that software engineers need to understand to make correct security decisions — not to implement cryptographic algorithms, but to choose and configure the right primitives, understand their properties and limitations, and avoid common misuse mistakes. Most cryptographic vulnerabilities come from developers using the wrong primitive, misusing a correct primitive, or rolling their own implementations. This entry is a decision guide and vocabulary reference for the cryptographic building blocks used in modern applications.

## When to Apply
- When choosing how to store passwords or sensitive data
- When designing token schemes (JWTs, API keys, session tokens)
- When implementing or reviewing TLS configuration
- When evaluating cryptographic library choices

## Key Concepts
- **Hash Functions (One-Way)**:
  - Convert arbitrary input to fixed-length output; one-way (cannot reverse to get input)
  - *Cryptographic hashes* (SHA-256, SHA-3): Collision-resistant; used for data integrity verification, digital signatures, content hashing. Not suitable for passwords alone — too fast, enabling brute-force
  - *MD5, SHA-1*: Cryptographically broken for collision resistance. Do not use for security. Acceptable only for checksums/non-security uses
  - *Password hashing* (Argon2id, bcrypt, scrypt): Deliberately slow and memory-hard; designed specifically for password storage. Always use these, never raw SHA for passwords
- **Symmetric Encryption**: Same key encrypts and decrypts. Fast; used for encrypting large data
  - *AES-256-GCM*: The standard. GCM mode provides both confidentiality and authentication (AEAD). Use this
  - *ChaCha20-Poly1305*: Alternative to AES; excellent on devices without AES hardware acceleration
  - *Avoid*: ECB mode (reveals patterns), CBC without authentication (padding oracle attacks), DES/3DES (obsolete)
  - Key concern: securely distributing the shared key. Use KMS or envelope encryption
- **Asymmetric (Public Key) Encryption**: Key pair — public key encrypts; private key decrypts. Slow; used for key exchange and digital signatures
  - *RSA-2048/4096*: Widely supported; slower than elliptic curve
  - *Elliptic Curve (ECC)*: Smaller keys, faster operations, equivalent security to RSA at much smaller key sizes. Ed25519 for signatures; X25519 for key exchange
  - Use for: TLS certificates, SSH keys, JWT signing (RS256 or ES256), PGP email encryption
- **Digital Signatures**: Prove that data was created by the holder of a private key and has not been tampered with. Used in TLS certificates, JWTs, code signing, git commits. Asymmetric — sign with private key; verify with public key
- **HMAC (Hash-based Message Authentication Code)**: A keyed hash — proves data integrity AND that the signer had the shared key. Used for JWT signature verification (HS256), webhook signature validation, API request signing. Symmetric — both parties need the shared key
- **Key Derivation Functions (KDF)**: Derive cryptographic keys from passwords or other input (PBKDF2, Argon2, HKDF). Used when you need a cryptographic key from a non-random input. Argon2id is the recommended KDF for password-derived keys
- **Random Number Generation**: Use cryptographically secure random number generators (CSPRNG) for all security-sensitive values:
  - Python: `secrets.token_hex()`, `os.urandom()`
  - Node.js: `crypto.randomBytes()`
  - Go: `crypto/rand`
  - Never use `Math.random()` or `random.random()` for security-sensitive values
- **TLS (Transport Layer Security)**: The protocol securing HTTPS and other network connections. Uses asymmetric crypto for key exchange; symmetric crypto for data encryption; MACs for integrity. TLS 1.3 is the current standard; disable TLS 1.0 and 1.1
- **Common Mistakes**:
  - Using the same nonce/IV twice with a symmetric cipher (breaks confidentiality)
  - Comparing hash values with `==` instead of a constant-time comparison (timing attack)
  - Storing symmetric keys in application code or environment variables (use KMS)
  - Using ECB mode for block cipher encryption (leaks data patterns)

## In Practice
Method uses AES-256-GCM via AWS Encryption SDK for application-layer encryption. Argon2id for password hashing. JWT signatures use RS256 (asymmetric) for cross-service tokens and HS256 (HMAC) for short-lived, single-service tokens. CSPRNG (`secrets` module in Python) for all token generation. TLS 1.2 minimum; TLS 1.3 preferred; enforced via ALB security policy.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Cryptography Fundamentals**: Never roll your own cryptography — use vetted libraries (libsodium, AWS Encryption SDK) and standard algorithms. The rule for symmetric encryption is AES-256-GCM; the rule for password storage is Argon2id; the rule for random tokens is CSPRNG. MD5 and SHA-1 are broken for security purposes — use SHA-256 or better. When in doubt about algorithm choice, use the library's recommended defaults — they're set to reasonable secure values. Use constant-time comparison for all hash/token validation to prevent timing attacks. → `engineering-knowledge-repository/cryptography-fundamentals.md`

## Related Entries
- [Encryption](encryption.md) — encryption in practice: TLS, at-rest encryption, KMS key management
- [JWT](jwt.md) — JWTs use HMAC (HS256) or RSA/ECDSA (RS256/ES256) signatures
- [Session Management](session-management.md) — session tokens require CSPRNG generation and secure storage
- [mTLS](mtls.md) — mutual TLS uses asymmetric cryptography for service-to-service authentication
- [Secrets Management](secrets-management.md) — cryptographic keys are secrets that require the same protection as credentials

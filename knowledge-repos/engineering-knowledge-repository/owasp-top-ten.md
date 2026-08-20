---
id: owasp-top-ten
tags: [reference, security, backend]
surfaces-at: [nfr-requirements, functional-design, code-generation]
related: [defense-in-depth, api-security, secrets-management, rbac]
complexity: foundational
---

# OWASP Top Ten

## What It Is
The Open Web Application Security Project's list of the ten most critical web application security risks, updated periodically based on industry data. The OWASP Top Ten is the most widely referenced security baseline for web applications. Understanding these vulnerabilities — and how to prevent them — is the minimum security literacy expected of all software engineers.

## When to Apply
- Security reviews of any web application or API
- Code review checklists — verify each category is addressed
- NFR Requirements — define which controls address each applicable Top Ten risk
- Training and onboarding — the Top Ten is the starting framework for security education

## When Not to Apply
- The Top Ten are a baseline, not a ceiling — high-security systems require threat modeling beyond the Top Ten

## Key Concepts (2021 Top Ten)

- **A01: Broken Access Control** — The most common. Authorization failures allowing users to access data or functions they shouldn't. Prevention: enforce access control server-side, deny by default.
- **A02: Cryptographic Failures** — Sensitive data transmitted or stored without adequate encryption. Prevention: TLS everywhere, encrypt data at rest, don't roll your own crypto.
- **A03: Injection** — SQL, NoSQL, OS, LDAP injection via untrusted data interpreted as commands. Prevention: parameterized queries, prepared statements, ORMs.
- **A04: Insecure Design** — Architecture-level security gaps. Prevention: threat modeling, secure design patterns, security requirements.
- **A05: Security Misconfiguration** — Default credentials, verbose error messages, unnecessary features enabled. Prevention: hardened configurations, infrastructure automation.
- **A06: Vulnerable Components** — Using components with known vulnerabilities. Prevention: keep dependencies up-to-date, use `dependabot` / `snyk`.
- **A07: Identification and Authentication Failures** — Broken auth, weak passwords, missing MFA. Prevention: strong auth, MFA, secure session management.
- **A08: Software and Data Integrity Failures** — Insecure CI/CD pipelines, auto-updates without integrity checks. Prevention: sign artifacts, verify integrity.
- **A09: Security Logging and Monitoring Failures** — Insufficient logging to detect breaches. Prevention: log security events, alert on anomalies, audit trails.
- **A10: SSRF (Server-Side Request Forgery)** — Application fetches user-supplied URLs, enabling internal network access. Prevention: allowlist valid URLs, block internal addresses.

## In Practice
OWASP Top Ten is Method's security code review checklist. Every application should be evaluated against each category. Automated tooling covers some risks (Dependabot for A06, static analysis for injection patterns) but design-level risks (A04, A01) require manual review.

## Engineering Knowledge
💡 **Engineering Knowledge — OWASP Top Ten**: Know these ten. Broken Access Control (#1) and Injection (#3) are responsible for a massive proportion of real breaches. Parameterize every query, enforce authorization server-side, encrypt everything in transit and at rest, keep dependencies updated, and log security events. Add OWASP ZAP or Burp Suite to your QA pipeline for dynamic scanning. These aren't advanced topics — they're baseline hygiene. → `engineering-knowledge-repository/security/owasp-top-ten.md`

## Related Entries
- [Defense in Depth](defense-in-depth.md) — OWASP Top Ten defines the attack classes that defense-in-depth layers must cover
- [API Security](api-security.md) — applies OWASP Top Ten principles specifically to API design
- [Secrets Management](secrets-management.md) — addresses A02 (Cryptographic Failures) and A05 (Security Misconfiguration)

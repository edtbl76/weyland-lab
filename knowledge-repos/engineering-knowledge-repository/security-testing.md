---
id: security-testing
tags: [methodology, security, testing, deployment]
surfaces-at: [application-design, infrastructure-design]
related: [owasp-top-ten, dependency-management, supply-chain-security, threat-modeling, ci-cd]
complexity: intermediate
---

# Security Testing

## What It Is
The set of automated and manual techniques for identifying security vulnerabilities in software before they reach production — or before attackers find them. Security testing spans static analysis of source code (SAST), dynamic testing of running applications (DAST), dependency vulnerability scanning, infrastructure configuration scanning, and manual penetration testing. Integrating security testing into CI/CD pipelines shifts vulnerability detection left — finding issues during development is orders of magnitude cheaper than finding them in production.

## When to Apply
- In every CI/CD pipeline (automated security scanning is a CI gate)
- Before any major release or feature launch
- After significant architecture changes
- As part of compliance requirements (SOC 2, PCI, HIPAA, FedRAMP)
- Periodically as scheduled security reviews

## Key Concepts
- **SAST (Static Application Security Testing)**: Analyzes source code without executing it. Finds: SQL injection patterns, hardcoded secrets, insecure function usage, common vulnerability patterns. Tools: Semgrep (fast, rule-based, open source), CodeQL (GitHub Advanced Security), Checkmarx, Veracode. Run in CI on every PR; fast feedback loop
  - Strength: Finds issues early; broad language support; integrates with PRs
  - Weakness: High false-positive rate; doesn't catch runtime or configuration issues
- **DAST (Dynamic Application Security Testing)**: Tests a running application by sending malicious inputs and observing responses. Finds: XSS, SQL injection, authentication flaws, misconfigured headers, open redirects. Tools: OWASP ZAP (open source), Burp Suite (manual + automated), Nuclei
  - Run against staging environment as part of CI/CD or scheduled scans
  - Strength: Finds real exploitable vulnerabilities; lower false-positive rate
  - Weakness: Slower than SAST; requires a running application; may not cover all code paths
- **Dependency Scanning**: Checks third-party dependencies against known vulnerability databases (CVE, GitHub Advisory). Tools: Snyk, Dependabot, OWASP Dependency-Check, `npm audit`, `pip-audit`. Block on critical/high severity; triage and fix medium/low. See [Dependency Management](dependency-management.md)
- **Secret Scanning**: Detects accidentally committed secrets (API keys, passwords, tokens) in Git history and code. Tools: GitHub Secret Scanning (automatic), truffleHog, gitleaks. Run pre-commit and in CI. Rotate any secrets found — assume they are compromised
- **Container Image Scanning**: Scan Docker images for OS-level CVEs and misconfigured Dockerfiles. Tools: Trivy (fast, open source), Grype, Snyk Container, Amazon ECR enhanced scanning. Block deployments with critical CVEs. Scan base images and rebuild regularly as OS packages receive security patches
- **Infrastructure Configuration Scanning**: Check IaC and cloud configuration for security misconfigurations. Tools: Checkov (Terraform/CloudFormation), tfsec, AWS Security Hub, CloudSploit. Findings: public S3 buckets, unencrypted storage, overly permissive IAM, missing VPC flow logs
- **IAST (Interactive Application Security Testing)**: Instruments running application code to detect vulnerabilities as tests execute. Combines SAST accuracy with DAST runtime context. Tools: Contrast Security, Seeker. Less common due to instrumentation complexity
- **Penetration Testing**: Manual security testing by a skilled attacker (internal red team or external firm). Finds complex vulnerabilities that automated tools miss: business logic flaws, chained exploits, social engineering risks. Typically annual or before major launches. Distinct from automated scanning — complements but does not replace it
- **Security in PR Reviews**: Security-focused checklist items in code review templates: Does this handle user input safely? Does this expose new attack surface? Does this change authentication or authorization logic? Are secrets handled correctly?

## In Practice
Method integrates Semgrep SAST, Snyk dependency scanning, and Trivy container scanning in all CI pipelines as required gates — PRs fail on critical findings. Secret scanning is enabled at the GitHub organization level. OWASP ZAP runs against staging on a nightly schedule. Checkov scans Terraform before `apply`. Annual penetration tests by an external firm cover critical applications. Security findings feed into a centralized Jira board with SLA by severity (critical: 24h, high: 7 days, medium: 30 days).

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Security Testing**: SAST + dependency scanning + secret scanning in CI is the minimum viable security testing posture — these take minutes to run and catch a meaningful class of vulnerabilities. SAST has high false-positive rates; tune rules to the noise level your team will actually act on. Container image scanning before deployment is critical: OS vulnerabilities in base images accumulate quickly and are trivially exploitable. Automated testing does not replace penetration testing — automated tools miss business logic flaws and chained vulnerabilities that a skilled attacker would find. Treat every discovered credential in Git history as compromised and rotate it immediately. → `engineering-knowledge-repository/security-testing.md`

## Related Entries
- [OWASP Top Ten](owasp-top-ten.md) — OWASP Top Ten defines the vulnerability categories that SAST and DAST tools target
- [Dependency Management](dependency-management.md) — dependency scanning is one pillar of the security testing stack
- [Supply Chain Security](supply-chain-security.md) — container scanning and secret scanning protect the software supply chain
- [Threat Modeling](threat-modeling.md) — threat modeling identifies what to test; security testing validates that the threats are mitigated
- [CI/CD](ci-cd.md) — security testing runs as CI gates integrated into the deployment pipeline

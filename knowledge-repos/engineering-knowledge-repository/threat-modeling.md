---
id: threat-modeling
tags: [methodology, security]
surfaces-at: [nfr-requirements, application-design, infrastructure-design]
related: [defense-in-depth, zero-trust-security, owasp-top-ten, api-security]
complexity: intermediate
---

# Threat Modeling

## What It Is
A structured process for identifying, analyzing, and mitigating security threats before they are implemented. Threat modeling is done at design time — before code is written — by systematically asking: "What can go wrong?" The output is a list of threats, their severity, and mitigating controls. STRIDE is the most widely used threat modeling framework (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege).

## When to Apply
- During application design for any system handling sensitive data or performing privileged operations
- When designing new authentication or authorization flows
- Before launching new external-facing APIs or services
- When making significant architectural changes that affect trust boundaries

## When Not to Apply
- Trivial internal tooling with no sensitive data or privileged operations
- When used as a checkbox exercise rather than genuine security analysis

## Key Concepts
- **STRIDE**: Microsoft's threat taxonomy — Spoofing (impersonation), Tampering (data modification), Repudiation (deny actions), Information Disclosure (data leaks), Denial of Service (availability), Elevation of Privilege (gain unauthorized permissions)
- **Trust Boundary**: A boundary where data or control crosses from one trust level to another — user to API, API to database, internal to external network. Threats most commonly occur at boundaries
- **Data Flow Diagram (DFD)**: A diagram of the system showing processes, data stores, data flows, and external entities — the foundation of threat model analysis
- **DREAD (deprecated)**: An older risk scoring model (Damage, Reproducibility, Exploitability, Affected users, Discoverability) — largely replaced by CVSS
- **CVSS (Common Vulnerability Scoring System)**: Industry-standard severity scoring for vulnerabilities — base score, temporal score, environmental score
- **Mitigating Control**: A countermeasure that reduces the likelihood or impact of a threat — encryption, authentication, input validation, logging
- **PASTA (Process for Attack Simulation and Threat Analysis)**: A risk-centric threat modeling methodology — more comprehensive than STRIDE, more suited for large systems
- **Threat Modeling Tools**: OWASP Threat Dragon, Microsoft Threat Modeling Tool — help generate DFDs and enumerate STRIDE threats automatically

## In Practice
Method incorporates threat modeling as part of the NFR Requirements stage for systems with security NFRs. A lightweight STRIDE analysis against the system's data flow diagram is the standard artifact. Each identified threat is documented with severity (CVSS score) and the planned mitigating control. Threat models are stored in `aidlc-docs/` and revisited when architecture changes.

## Engineering Knowledge
💡 **Engineering Knowledge — Threat Modeling**: Security analysis done at design time is 100x cheaper than post-deployment fixes. Apply STRIDE to your data flow diagram — for each data flow, ask whether Spoofing, Tampering, Repudiation, Info Disclosure, DoS, or Privilege Escalation is possible. Focus on trust boundaries — that's where threats concentrate. Document each threat, assign a CVSS severity, specify the mitigating control. OWASP Threat Dragon is a free tool that guides this process. Do this before building, not after. → `engineering-knowledge-repository/security/threat-modeling.md`

## Related Entries
- [Defense in Depth](defense-in-depth.md) — threat modeling informs which defensive layers are needed
- [Zero Trust Security](zero-trust-security.md) — threat modeling often reveals implicit trust that zero trust eliminates
- [OWASP Top Ten](owasp-top-ten.md) — OWASP Top Ten provides a baseline threat checklist for web applications
- [API Security](api-security.md) — APIs are high-priority trust boundaries in threat models

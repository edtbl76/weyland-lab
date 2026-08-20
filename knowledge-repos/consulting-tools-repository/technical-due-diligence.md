---
id: technical-due-diligence
tags: [technology-assessment, strategy, risk]
surfaces-at: [validated-intent, requirements-analysis]
related: [build-buy-partner, tech-radar, magic-quadrant, architecture-tradeoff-analysis]
complexity: intermediate
---

# Technical Due Diligence

## What It Is
A structured assessment of a technology organization's assets, liabilities, and capabilities — typically conducted in M&A contexts (acquiring a software company), vendor evaluations (before a major platform commitment), or existing-system assessments (before a transformation program). Technical due diligence evaluates: code quality and maintainability, architecture and scalability, security posture, technology stack currency, team capability, technical debt, IP ownership, licensing compliance, and operational maturity. The output is a risk-adjusted view of the technology asset's true value and the investment required to realize it.

## When to Use
- Pre-acquisition or investment assessment of a technology company or product
- Before committing to a major vendor platform (is this vendor's technology viable long-term?)
- At the start of a transformation program to establish the true baseline of the existing system
- When a client is considering acquiring or merging with a company and needs an independent technology view
- Evaluating a startup's technology claims before a partnership or licensing agreement

## Key Concepts
- **Code Quality Assessment**: Static analysis, test coverage, code complexity (cyclomatic complexity, coupling), documentation quality. Red flags: near-zero test coverage, high duplication, no CI/CD
- **Architecture Review**: Scalability headroom, modularity, database design, integration patterns, use of standards vs. proprietary approaches. Red flags: Big Ball of Mud, undocumented integrations, monolithic database shared across systems
- **Security Posture**: Dependency vulnerability scan, authentication/authorization patterns, secrets management, data handling compliance (PCI-DSS, HIPAA, GDPR). Red flags: hardcoded credentials, unpatched CVEs in dependencies, no audit logging
- **Technology Stack Currency**: Are the languages, frameworks, and infrastructure still actively maintained and in broad adoption? Red flags: end-of-life dependencies, unsupported operating systems, deprecated cloud services
- **Technical Debt Quantification**: Estimate the investment required to reach an acceptable baseline — not to make it perfect, but to make it maintainable and extensible. Often expressed as months of engineering effort
- **Team Assessment**: Capability, seniority mix, retention risk, key-person dependency (single engineers who understand critical systems). Red flags: one-person knowledge silos, no documentation
- **IP and Licensing**: Open source license compliance (GPL obligations), third-party IP in the codebase, patent exposure. Red flags: GPL-licensed code embedded in commercial products, unlicensed commercial components
- **Operational Maturity**: Monitoring, alerting, runbooks, incident response, deployment practices. Red flags: no observability, manual deployments, no disaster recovery testing

## Method Application
Method conducts technical due diligence as a standalone engagement or as the opening phase of a transformation program. The deliverable is a scored assessment across dimensions, a risk register, and a prioritized remediation roadmap with cost estimates. Presented to executive stakeholders as input to investment or acquisition decisions.

## Consulting Insight
🎯 **Consulting Tool — Technical Due Diligence**: The most common finding in technical due diligence is a gap between the technology's external presentation and its internal reality — demos are polished; the codebase is not. Focus the assessment on the five highest-risk areas for the specific context: for M&A it's IP/licensing and key-person risk; for transformation it's technical debt and architecture; for vendor evaluation it's security and scalability. Always produce a quantified remediation cost estimate, not just a risk list — executives need to make financial decisions with the output. → `consulting-tools-repository/technical-due-diligence.md`

## Related Entries
- [Build vs. Buy vs. Partner](build-buy-partner.md) — due diligence findings directly inform build/buy decisions
- [Tech Radar](tech-radar.md) — stack currency assessment draws on radar for technology lifecycle context
- [Architecture Tradeoff Analysis](architecture-tradeoff-analysis.md) — ATAM-style analysis is part of architecture review in a due diligence

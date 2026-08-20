---
id: lending
vertical: financial-services
tags: [financial-services, lending, credit, origination, underwriting, servicing]
surfaces-at: [application-design, functional-design]
related: [financial-services-overview, kyc-aml, payments-processing, dynamic-configuration-management]
---

# Lending

## What It Is
Lending technology covers the systems that support the full credit lifecycle — origination (acquiring and processing loan applications), underwriting (credit decisioning), closing (disbursement), and servicing (ongoing payment management, collections, and payoff). Participants range from traditional banks and credit unions to non-bank lenders, fintechs, and embedded lending platforms. Product types span personal loans, auto loans, mortgages, student loans, small business lending, and BNPL (Buy Now Pay Later).

## Why It Matters in Financial Services
Lending is one of the largest revenue lines in financial services. The technology that supports it directly affects conversion rates (application to funded loan), credit loss rates (underwriting accuracy), and servicing costs. Regulatory compliance is pervasive — Truth in Lending Act (TILA), Equal Credit Opportunity Act (ECOA), Fair Credit Reporting Act (FCRA), and state-specific usury and licensing laws govern every stage of the lifecycle. Discrimination in credit decisioning (disparate impact) is a major regulatory and reputational risk.

## Key Concepts
- **Loan Origination System (LOS)**: The platform managing the application workflow — data collection, document upload, verification, decisioning, and closing. Encompasses the borrower-facing application and the lender's back-office workflow. Major platforms: Encompass (ICE Mortgage), nCino, Blend, Finastra.
- **Credit Bureau / Credit Report**: The data source for underwriting — FICO score, payment history, outstanding balances, derogatory marks. The three major bureaus (Experian, Equifax, TransUnion) provide reports via API. Soft vs hard pull distinction matters for FCRA compliance.
- **Underwriting Engine / Decision Engine**: Rules-based or ML-based system that evaluates creditworthiness and produces a credit decision (approve/decline/counter-offer) and pricing (interest rate, terms). Must be explainable for adverse action notice compliance.
- **Adverse Action Notice**: When a credit application is declined or offered worse terms, ECOA and FCRA require a written notice with specific reasons. The underwriting engine must generate auditable, regulation-compliant reason codes — not opaque ML outputs.
- **Loan Servicing System (LSS)**: The platform managing funded loans — payment scheduling, payment processing, escrow (for mortgages), delinquency management, collections, modifications, and payoff. Major platforms: Black Knight MSP, Sagent, FiServ LoanServ.
- **DTI / LTV**: Debt-to-Income ratio and Loan-to-Value ratio — the two primary underwriting metrics. DTI measures affordability (monthly debt obligations ÷ income). LTV measures collateral coverage (loan amount ÷ asset value). Both have regulatory and risk thresholds.
- **Waterfall / Fallback Logic**: Decisioning logic that tries multiple credit strategies in sequence — primary bureau pull → alternative data → manual review. Each step handles applications that the previous step could not decisively approve or decline.
- **HMDA (Home Mortgage Disclosure Act)**: Federal reporting requirement for mortgage lenders — requires reporting of applicant demographics, loan characteristics, and disposition. Used by regulators to detect discriminatory lending patterns.

## Common Patterns / Gotchas
- **Adverse action reason codes require explainability by design.** Black-box ML models that cannot produce regulation-compliant reason codes are not deployable in consumer lending without an explainability layer. Build this in before the model, not after.
- **Income and identity verification are third-party dependencies.** Payroll data (The Work Number, Argyle, Pinwheel), bank account verification (Plaid, MX), and identity verification (Socure, Persona) are typically provided by vendors. Each has its own API, coverage gaps, and failure modes.
- **Servicing data migration is high-risk.** Moving a loan portfolio between servicing systems requires migrating complex, legally-binding financial records — payment history, escrow balances, amortization schedules. Data integrity errors have regulatory and financial consequences.
- **State licensing creates geographic complexity.** Lending licenses are state-specific. A lender operating in all 50 states has 50 sets of rate caps, disclosure requirements, and regulatory obligations. The origination system must enforce geographic rules without hardcoding them.
- **BNPL has distinct regulatory treatment.** BNPL products occupy an evolving regulatory space — CFPB is actively developing guidance. BNPL platforms should be designed for regulatory adaptability, not against a fixed compliance assumption.

## Industry Insight
💳 **Industry Insight — Lending**: You're designing a lending system. Adverse action reason code generation must be designed alongside the underwriting model, not retrofitted — ECOA compliance requires explainable, regulation-compliant decline reasons for every credit decision. State-specific lending rules (rate caps, disclosures, licensing) must be configuration-driven, not hardcoded — the lender's geographic footprint will change. Servicing system data migration carries material financial and regulatory risk; treat it as the highest-risk workstream in any lending platform program. → `industry-vertical-repository/financial-services/lending.md`

## Solutions Context
**Typical engagement patterns**: Digital loan origination platform, underwriting engine modernization, lending API platform (embedded finance), servicing system migration, BNPL platform.

**Common scope anchors**: Application workflow (LOS), credit bureau integration, underwriting/decision engine, adverse action compliance, income and identity verification, loan servicing integration, state rules engine.

**Risk factors**: Adverse action explainability requires ML model and compliance design to be coordinated from the start. Servicing data migration scope and risk expands with portfolio complexity. Third-party data vendor coverage gaps (income verification, identity) create decisioning gaps that must be handled.

## Related Entries
- [Financial Services Overview](_overview.md)
- [KYC/AML](kyc-aml.md)
- [Payments Processing](payments-processing.md)
- [Dynamic Configuration Management](../../engineering-knowledge-repository/dynamic-configuration-management.md) — state-specific lending rules (rate caps, disclosures, licensing) must be configuration-driven; the lender's geographic footprint changes

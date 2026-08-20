---
id: kyc-aml
vertical: financial-services
tags: [financial-services, kyc, aml, compliance, identity, onboarding, fraud]
surfaces-at: [application-design, functional-design]
related: [financial-services-overview, payments-processing]
---

# KYC / AML

## What It Is
Know Your Customer (KYC) is the process of verifying the identity of customers at onboarding and on an ongoing basis. Anti-Money Laundering (AML) is the broader compliance program for detecting and reporting suspicious financial activity. Together, KYC/AML is the compliance backbone of every financial institution — banks, broker-dealers, money services businesses, crypto exchanges, and increasingly fintech platforms. It is both a regulatory obligation and a fraud prevention control.

## Why It Matters in Financial Services
The Bank Secrecy Act (BSA), USA PATRIOT Act, and FinCEN regulations require financial institutions to implement AML programs. Failure results in material fines (HSBC: $1.9B, TD Bank: $3B+), regulatory sanctions, and in extreme cases criminal liability for executives. AML programs are scrutinized by regulators (OCC, FinCEN, state banking regulators) in regular examinations. The technology that supports KYC/AML must be both effective (detecting real risk) and defensible (documented, auditable, and explainable to examiners).

## Key Concepts
- **CDD (Customer Due Diligence)**: The baseline KYC process — collecting and verifying customer identity, understanding the nature of the customer's business, and assessing risk. Required for all customers.
- **EDD (Enhanced Due Diligence)**: Deeper investigation required for higher-risk customers — PEPs (Politically Exposed Persons), high-value accounts, customers in high-risk jurisdictions, money services businesses.
- **PEP (Politically Exposed Person)**: A person who holds or has held a prominent public position — heads of state, senior politicians, military officials, judiciary. PEPs and their associates require EDD and ongoing monitoring due to corruption risk.
- **OFAC Screening**: Screening customers and transactions against OFAC (Office of Foreign Assets Control) sanctions lists. Legally required; violations are strict liability. Must happen at onboarding and on an ongoing basis as sanctions lists change.
- **Watchlist Screening**: Broader screening beyond OFAC — including Interpol notices, adverse media, and other regulatory watchlists. Vendor solutions: Refinitiv World-Check, Dow Jones, LexisNexis.
- **SAR (Suspicious Activity Report)**: A report filed with FinCEN when a financial institution detects suspicious activity that may constitute money laundering, fraud, or other financial crime. Filing SARs is a legal obligation; timing and content requirements are strict.
- **Transaction Monitoring**: Ongoing analysis of customer transaction patterns to detect anomalies consistent with money laundering — structuring (breaking large amounts into smaller deposits), layering, smurfing. Rule-based and ML-based approaches are both used.
- **Risk Scoring**: A model that assigns each customer a risk score based on factors like geography, industry, transaction patterns, and adverse events. High-risk customers trigger EDD and more frequent reviews.
- **Beneficial Ownership**: The requirement (FinCEN CDD Rule) to identify and verify the natural persons who own or control a legal entity customer — specifically, any individual owning 25%+ of a company.

## Common Patterns / Gotchas
- **Regulatory expectations are process-based, not just technology-based.** Examiners review whether the institution has a documented, consistently applied AML program — not just whether the software works. Documentation, procedures, training records, and audit trails are part of the compliance posture.
- **False positive rate is the operational burden.** AML systems that generate too many false alerts overwhelm compliance teams. Tuning the alert threshold and model is an ongoing operational function, not a one-time configuration. Build feedback loops and tuning workflows into the system.
- **Sanctions screening must be near-real-time.** OFAC screening of transactions cannot wait for batch processing — a transaction that clears before screening is a violation. Screening must be synchronous with transaction flow for payments.
- **Identity document verification is a third-party dependency.** Document OCR, liveness detection, and identity verification against authoritative sources (SSA, DMV, credit bureaus) are typically provided by vendors (Jumio, Onfido, Socure, Persona). Evaluate vendor accuracy, coverage, and API quality carefully.
- **AML model explainability matters for examinations.** Black-box ML models that generate alerts without explainable rationale are difficult to defend to regulators. Hybrid approaches (rule-based detection + ML scoring) with documented alert rationale are more defensible.
- **Case management is as important as detection.** Generating a SAR requires a documented investigation workflow — alert review, customer due diligence, escalation, approvals, and filing. Case management system design is a significant scope item.

## Industry Insight
💳 **Industry Insight — KYC/AML**: You're building KYC or AML systems. AML compliance is a documented program as much as a technology solution — the audit trail, case management workflow, and SAR filing process are regulatory deliverables, not operational nice-to-haves. OFAC sanctions screening must be synchronous with payment processing, not batch; design this into the payments flow architecture. False positive management (alert tuning, feedback loops) must be a first-class capability, not an afterthought — compliance team capacity is the operational constraint. → `industry-vertical-repository/financial-services/kyc-aml.md`

## Solutions Context
**Typical engagement patterns**: KYC/onboarding platform, AML transaction monitoring, sanctions screening integration, beneficial ownership management, case management for SAR filing, compliance program modernization.

**Common scope anchors**: Identity verification workflow (CDD/EDD), OFAC and watchlist screening integration, transaction monitoring rules and ML model, risk scoring, case management and SAR workflow, audit logging.

**Risk factors**: Regulatory examination readiness requires documentation and process design beyond the software itself. Identity verification vendor API quality and coverage vary significantly. False positive rates are difficult to predict without historical transaction data for model tuning.

## Related Entries
- [Financial Services Overview](_overview.md)
- [Payments Processing](payments-processing.md)

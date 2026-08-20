---
id: financial-services-overview
vertical: financial-services
tags: [financial-services, banking, fintech, payments, compliance, overview]
surfaces-at: [requirements-analysis, application-design]
related: [payments-processing]
---

# Financial Services — Industry Overview

## What It Is
Financial services spans banking (retail, commercial, investment), insurance, capital markets, and fintech. Engagements may sit inside a regulated institution (bank, insurer, broker-dealer) or in a fintech building on top of regulated infrastructure. The distinction matters: a bank building internal tooling and a fintech accessing banking rails have very different compliance obligations and integration patterns.

## Why It Matters
Financial services is heavily regulated at both federal and state levels, and in most cases internationally as well. The regulatory surface area — SOX, PCI-DSS, BSA/AML, GLBA, FINRA, OCC — is wide, and non-compliance carries material financial and reputational consequences. Architecture decisions that seem purely technical (where data is stored, how keys are managed, what audit trail exists) often have direct regulatory implications.

## Key Concepts
- **PCI-DSS**: Payment Card Industry Data Security Standard. Governs any system that stores, processes, or transmits cardholder data. Compliance is mandatory for card payments; scoping PCI correctly (minimizing the cardholder data environment) is a key architectural concern.
- **BSA / AML (Bank Secrecy Act / Anti-Money Laundering)**: Federal requirements for financial institutions to detect and report suspicious activity. KYC (Know Your Customer) is the customer identity component of AML compliance.
- **SOX (Sarbanes-Oxley)**: Governs financial reporting controls for public companies. Relevant to any system that feeds financial data upstream.
- **GLBA (Gramm-Leach-Bliley Act)**: Governs how financial institutions handle consumer financial data. Analogous to HIPAA in healthcare.
- **Core Banking System**: The system of record for accounts, balances, and transactions. Temenos, FIS, Fiserv, and Jack Henry are common vendors. Core integrations are typically complex and slow.
- **Ledger**: The authoritative record of all financial transactions. Double-entry accounting is the foundation. Any system that moves money must maintain a correct ledger.
- **Settlement vs Clearing**: Clearing is the reconciliation and confirmation of a transaction. Settlement is the actual transfer of funds. These are not simultaneous — the gap between them is a risk surface.

## Common System Archetypes
- **Payments Platform**: Orchestrates money movement across rails (ACH, card, wire, RTP)
- **KYC / Onboarding Platform**: Customer identity verification and risk scoring at account opening
- **Fraud Detection System**: Real-time and batch analytics to detect fraudulent transactions
- **Lending Platform**: Loan origination, underwriting, and servicing
- **Trading / Order Management System**: Order routing, execution, and position management for capital markets

## Common Integration Points
- **ACH (Automated Clearing House)**: Batch payment network for US bank transfers. NACHA rules govern file format and timing.
- **Card Networks (Visa/Mastercard)**: Authorization, clearing, and settlement for card payments. ISO 8583 message format.
- **SWIFT**: International wire transfer network. ISO 20022 is the modern message standard replacing MT messages.
- **RTP (Real-Time Payments)**: The Clearing House's instant payment rail. ISO 20022, 24/7/365, irrevocable.
- **FedNow**: Federal Reserve's instant payment service. Also ISO 20022.
- **Open Banking APIs**: OAuth2-based APIs for account data access and payment initiation (Plaid, MX, or direct bank APIs).

## Industry Insight
💳 **Industry Insight — Financial Services**: You're working in financial services. Before designing any data model, identify which data is in scope for PCI-DSS (cardholder data) and which constitutes NPI under GLBA — these drive encryption, tokenization, and access control requirements. Any system that moves money needs a correct ledger; model the ledger explicitly, not as a side effect of transaction records. → `industry-vertical-repository/financial-services/_overview.md`

## Solutions Context
**Typical engagement patterns**: Payments platform modernization, KYC/AML compliance systems, fintech product builds, core banking integration layer, fraud detection, open banking API exposure.

**Common scope anchors**: PCI-DSS scoping and compliance posture, ledger design, payments rail integration (ACH/RTP/card), KYC/identity verification, fraud detection, audit logging for SOX/GLBA.

**Risk factors**: Core banking system integrations are frequently the long pole — vendor timelines and API maturity are often outside client control. PCI scope creep (accidentally including systems in the cardholder data environment) adds significant compliance overhead. Real-time payment rails (RTP, FedNow) are irrevocable — error handling and fraud prevention must be designed before go-live, not after.

**Estimation notes**: PCI-DSS compliance work should be scoped as a dedicated workstream. Core banking integrations should be treated as high-uncertainty until API documentation is reviewed. Any ledger or settlement work requires a dedicated accounting/finance domain expert in the design process.

## Related Entries
- [Payments Processing](payments-processing.md) — moving money across rails

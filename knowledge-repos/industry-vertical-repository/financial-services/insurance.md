---
id: insurance
vertical: financial-services
tags: [financial-services, insurance, claims, underwriting, policy, p&c, life]
surfaces-at: [application-design, functional-design]
related: [financial-services-overview, kyc-aml, payments-processing, strangler-fig]
---

# Insurance

## What It Is
Insurance technology covers the systems supporting the insurance lifecycle — product definition, distribution (quoting and binding), policy administration, claims management, and reinsurance. Lines of business include property and casualty (P&C: auto, home, commercial), life and annuity (L&A), health (distinct from healthcare delivery — this is the payer side), and specialty lines (cyber, marine, aviation). The technology landscape spans carriers (who bear risk), MGAs (Managing General Agents who underwrite on behalf of carriers), brokers, and insurtech platforms.

## Why It Matters in Financial Services
Insurance is a data and risk management business. The systems that collect risk data (underwriting), price it (rating), manage policies (PAS), and process claims directly determine combined ratio — the primary financial metric. Poor underwriting data quality leads to mispriced risk. Poor claims systems lead to overpayment, fraud, and customer attrition. Regulatory compliance (state DOI filings, rate approvals, claims handling laws) is extensive and jurisdiction-specific.

## Key Concepts
- **Policy Administration System (PAS)**: The system of record for all policies — terms, coverages, endorsements, premiums, and status. The operational backbone of a carrier or MGA. Legacy PAS platforms (Guidewire, Duck Creek, Majesco) are deeply entrenched and expensive to replace.
- **Rating Engine**: Calculates premium based on risk attributes (driver history, property location, credit score, claims history). Rating factors and algorithms are filed with state insurance departments for most personal and commercial lines — changes require regulatory approval.
- **Underwriting Workbench**: The tool used by underwriters to evaluate complex or non-standard risks, request additional information, apply judgment, and bind coverage. For commercial lines, human underwriting is the norm; personal lines are increasingly automated.
- **Claims Management System (CMS)**: Manages the end-to-end claims lifecycle — first notice of loss (FNOL), assignment, investigation, evaluation, settlement, and payment. Guidewire ClaimCenter is dominant. Claims is the largest cost center in insurance.
- **FNOL (First Notice of Loss)**: The initial report of a loss event. FNOL intake — by phone, app, or digital form — triggers the claims workflow. FNOL data quality determines how efficiently the claim can be investigated.
- **Subrogation**: The carrier's right to recover claim payments from a liable third party after paying the insured. Subrogation identification and recovery is a significant revenue recovery function.
- **Loss Reserve**: The actuarial estimate of future claim payments for reported but not yet settled claims (IBNR — Incurred But Not Reported). Reserve accuracy is a key financial statement and regulatory concern.
- **Reinsurance**: Insurance purchased by carriers to limit their exposure on large or catastrophic losses. Reinsurance treaties and facultative placements must be tracked and bordereaux (periodic reports to reinsurers) generated accurately.
- **ISO / ACORD Standards**: ACORD is the insurance industry's standards body for data exchange. ACORD XML messages and forms are the standard for insurance data exchange between carriers, agents, and MGAs.

## Common Patterns / Gotchas
- **Legacy PAS replacement is one of the highest-risk programs in any industry.** Guidewire and Duck Creek implementations are multi-year, nine-figure programs at large carriers. Data migration (policy history, claims history, financial records) carries enormous complexity. The strangler fig pattern is the standard approach — not big-bang replacement.
- **Rating engine changes require regulatory filings.** Any change to a filed rating algorithm requires state DOI approval before implementation. This creates months-long lead times for even minor rating changes. Rate change management must be a first-class capability.
- **Claims fraud is a significant cost driver.** Estimated at 10–20% of total claims cost. Fraud detection (rules-based and ML-based) at FNOL and during investigation is a high-ROI investment. SIU (Special Investigations Unit) workflow is part of claims management.
- **Straight-through processing (STP) rates are the key claims efficiency metric.** Claims that can be evaluated and settled without human intervention. Increasing STP requires high-quality FNOL data, accurate coverage verification, and reliable damage estimation. Each gap in automation creates a human touchpoint.
- **State-by-state compliance is unavoidable.** Insurance is regulated at the state level. A carrier writing in all 50 states manages 50 sets of rate filings, policy form approvals, claims handling laws, and market conduct requirements. Compliance infrastructure must be multi-jurisdictional by design.

## Industry Insight
💳 **Industry Insight — Insurance**: You're working in insurance. Legacy PAS migration (Guidewire, Duck Creek) is a multi-year program risk — use the strangler fig pattern and prioritize data migration planning as the first workstream. Rating engine changes in filed lines require state regulatory approval with lead times measured in months; build rate change management and filing workflow into the platform, not as an afterthought. Straight-through processing rate is the key claims automation metric — improving it requires high-quality FNOL data first; automate data collection before automating decisions. → `industry-vertical-repository/financial-services/insurance.md`

## Solutions Context
**Typical engagement patterns**: PAS modernization (Guidewire/Duck Creek implementation), digital distribution and quoting, claims automation and straight-through processing, fraud detection, MGA platform, insurtech product builds.

**Common scope anchors**: Policy administration (PAS integration or build), rating engine, digital FNOL, claims workflow automation, fraud detection, reinsurance bordereau, ACORD data exchange, state compliance rules engine.

**Risk factors**: PAS data migration scope and risk is the dominant delivery risk in any core systems program. Rating regulatory filing timelines are outside team control. Fraud detection model accuracy requires historical claims data for training.

## Related Entries
- [Financial Services Overview](_overview.md)
- [KYC/AML](kyc-aml.md)
- [Payments Processing](payments-processing.md)
- [Strangler Fig](../../engineering-knowledge-repository/strangler-fig.md) — the standard approach for legacy PAS replacement; big-bang replacement is high-risk at carrier scale

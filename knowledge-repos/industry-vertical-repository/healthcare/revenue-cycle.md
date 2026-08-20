---
id: revenue-cycle
vertical: healthcare
tags: [healthcare, rcm, revenue-cycle, claims, billing, coding, denial-management]
surfaces-at: [application-design, functional-design]
related: [healthcare-overview, prior-authorization, ehr-integration]
---

# Revenue Cycle Management (RCM)

## What It Is
Revenue Cycle Management (RCM) is the end-to-end financial process by which healthcare providers convert clinical services into collected revenue — from patient registration and insurance verification through clinical documentation, medical coding, claim submission, payment posting, and denial management. It is the financial backbone of every provider organization, and its performance directly determines whether a health system is financially viable.

## Why It Matters in Healthcare
Provider margins are thin — most health systems operate on 2–4% operating margins. Revenue leakage (claims that are denied, underpaid, or never submitted) directly threatens financial sustainability. Claim denial rates of 5–10% are common; each denied claim costs $25–$118 to rework. At scale, even a 1% improvement in clean claim rate translates to millions of dollars. RCM is a high-automation, high-ROI domain and one of the most active areas of healthcare technology investment.

## Key Concepts
- **Patient Access**: The front-end of RCM — scheduling, registration, insurance eligibility verification, prior authorization, and financial counseling. Errors here (incorrect insurance ID, missing authorization) are the primary source of downstream denials.
- **Medical Coding**: Translation of clinical documentation into standardized code sets — ICD-10-CM (diagnoses), CPT/HCPCS (procedures), DRG (inpatient episode grouping). Coding accuracy directly determines claim reimbursement. CDI (Clinical Documentation Improvement) programs improve documentation quality to support accurate coding.
- **Claim Scrubbing**: Automated pre-submission validation of claims against payer-specific rules — correct code combinations, required modifiers, valid NPI numbers, authorization on file. Scrubbing catches errors before submission, improving clean claim rates.
- **835 / 837**: The X12 EDI transaction sets for healthcare. 837 is the claim submission format (professional, institutional, dental). 835 is the remittance advice — the payer's response showing what was paid, adjusted, or denied and why. These are the primary data formats in provider billing.
- **ERA (Electronic Remittance Advice)**: The electronic version of the 835 — received from payers after claim adjudication. ERA processing (auto-posting payments and adjustments to the patient account) is a key automation opportunity.
- **Denial Management**: The workflow for identifying, categorizing, appealing, and resolving denied claims. Denial root cause analysis (why are claims being denied, and how to prevent recurrence) is the highest-value RCM function.
- **A/R (Accounts Receivable)**: Outstanding balances owed by payers and patients. A/R aging (how long balances have been outstanding) is the primary financial health metric. Days in A/R above 50 is a warning sign.
- **Charge Capture**: The process of recording all billable services delivered to a patient. Charge capture gaps (services delivered but not billed) are pure revenue leakage. EHR-integrated charge capture reduces gaps.
- **Contractual Adjustment**: The difference between the provider's billed charges and the allowed amount under the payer contract. Auto-posting contractual adjustments accurately requires maintaining current payer fee schedules in the billing system.

## Common Patterns / Gotchas
- **Eligibility verification at the point of scheduling prevents downstream denials.** The most cost-effective denial prevention happens before the patient arrives — verifying insurance, checking for active prior authorizations, and collecting copays. Eligibility verification integrated into scheduling workflows is high-ROI.
- **Denial categorization drives prevention.** Not all denials are equal — some are administrative (wrong insurance ID), some are clinical (not medically necessary), some are contractual (bundling rules). Categorizing denials accurately is the prerequisite for prevention programs. Generic "denial rates" without categorization are not actionable.
- **Payer contract management is a hidden complexity.** Each payer has a different fee schedule, different bundling rules, different timely filing deadlines, and different appeal procedures. Maintaining current payer rules in the billing system is an ongoing operational burden frequently handled manually.
- **Patient balance collection is increasingly important.** High-deductible health plans have shifted significant cost to patients. Patient A/R collection now requires a consumer-grade payment experience — payment plans, text-to-pay, price transparency — not just a paper statement.
- **RCM automation requires clean data upstream.** Intelligent denial prevention and auto-posting only work when registration data, coding, and clinical documentation are accurate. RCM automation programs must address data quality upstream, not just automate the billing layer.

## Industry Insight
🏥 **Industry Insight — Revenue Cycle Management**: You're working on healthcare RCM. Denial prevention is more valuable than denial rework — every dollar spent on eligibility verification, prior auth confirmation, and claim scrubbing at the front end avoids $25–$118 in rework cost on the back end. Denial categorization must be granular enough to drive prevention programs; aggregate denial rates are not actionable. Patient balance collection now requires a consumer-grade digital payment experience — paper statements generate the lowest collection rates and highest call center volume. → `industry-vertical-repository/healthcare/revenue-cycle.md`

## Solutions Context
**Typical engagement patterns**: RCM automation platform, denial management analytics, eligibility verification workflow, charge capture optimization, patient payment platform, prior auth integration into registration workflow.

**Common scope anchors**: 837/835 EDI processing, claim scrubbing rules engine, ERA auto-posting, denial categorization and workflow, eligibility verification integration, patient payment portal, payer contract fee schedule management.

**Risk factors**: Payer-specific rule variations are extensive and constantly changing — payer rules maintenance is an ongoing operational cost. RCM automation quality depends on upstream data quality (registration, coding) outside the billing system. Patient balance collection requires integration with the patient-facing portal and payment processor.

## Related Entries
- [Healthcare Overview](_overview.md)
- [Prior Authorization](prior-authorization.md)
- [EHR Integration](ehr-integration.md)

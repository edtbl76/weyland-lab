---
id: healthcare-overview
vertical: healthcare
tags: [healthcare, hipaa, fhir, hl7, overview]
surfaces-at: [requirements-analysis, application-design]
related: [prior-authorization, patient-identity]
---

# Healthcare — Industry Overview

## What It Is
Healthcare technology spans three primary segments: **providers** (hospitals, clinics, physician groups), **payers** (insurance companies, CMS, managed care organizations), and **health-tech** (digital health platforms, health information exchanges, medical device software). Engagements may touch one or all three, and the relationships between them — claims, prior authorization, referrals, care coordination — are often where the most complexity lives.

## Why It Matters
Healthcare is one of the most regulated industries in the US. Every system that touches patient data operates under HIPAA. Systems that interact with federal programs (Medicare, Medicaid) face additional CMS mandates. The regulatory landscape isn't just a compliance checkbox — it shapes system architecture, data residency decisions, vendor selection, and integration patterns.

## Key Concepts
- **PHI (Protected Health Information)**: Any individually identifiable health information. HIPAA governs how it's stored, transmitted, and accessed. De-identification is complex and has specific safe harbor rules.
- **Covered Entity / Business Associate**: Organizations that handle PHI. A BAA (Business Associate Agreement) is required between covered entities and their technology vendors. Method will typically be a Business Associate.
- **EHR (Electronic Health Record)**: The system of record for clinical data. Epic, Cerner (now Oracle Health), and Athenahealth dominate. EHR integration is almost always required.
- **HL7 / FHIR**: HL7 is the legacy healthcare messaging standard. FHIR (Fast Healthcare Interoperability Resources) is the modern REST-based standard mandated by CMS for interoperability. New integrations should default to FHIR R4.
- **CMS**: Centers for Medicare & Medicaid Services. Sets federal policy for payers and providers. CMS mandates (e.g., interoperability rules, prior auth rules) drive most large-scale healthcare IT initiatives.
- **Claims / Adjudication**: The process by which payers receive, evaluate, and pay (or deny) provider bills. X12 EDI (837/835 transactions) is the standard format.

## Common System Archetypes
- **Patient Portal**: Consumer-facing access to health records, scheduling, and messaging (often FHIR-backed)
- **Prior Authorization Platform**: Workflow system managing PA requests between providers and payers
- **Care Management Platform**: Tools for managing patients with chronic conditions or complex care needs
- **Health Information Exchange (HIE)**: Infrastructure for sharing patient data across organizations
- **Revenue Cycle Management (RCM)**: End-to-end billing and claims processing systems

## Common Integration Points
- **FHIR R4 APIs**: Standard for patient data, clinical resources, and payer interoperability
- **HL7 v2**: Legacy messaging still widely used for ADT (admit/discharge/transfer) events and lab results
- **X12 EDI**: Claims (837), remittance (835), prior auth (278), eligibility (270/271)
- **SMART on FHIR**: OAuth2-based authorization framework for EHR app integrations
- **Direct Messaging**: Secure email standard for provider-to-provider clinical communication

## Industry Insight
🏥 **Industry Insight — Healthcare**: You're working in healthcare. Before defining any data model, identify which fields constitute PHI — this determines encryption requirements, access controls, audit logging obligations, and which third-party vendors can touch the data. FHIR R4 is the right default for new integrations; HL7 v2 will likely appear in any brownfield context. → `industry-vertical-repository/healthcare/_overview.md`

## Solutions Context
**Typical engagement patterns**: EHR integration work, payer-provider interoperability, patient-facing digital health products, prior authorization automation, care management platforms.

**Common scope anchors**: HIPAA compliance posture review, FHIR API integration, patient identity / MPI, prior authorization workflows, CMS mandate alignment (interoperability rule, prior auth rule).

**Risk factors**: PHI handling requirements increase testing and security review scope significantly. EHR vendor timelines (Epic, Cerner) are often outside client control. Payer-specific variations add hidden complexity to any workflow that touches insurance.

**Estimation notes**: HIPAA compliance infrastructure (audit logging, encryption, access controls, BAA review) should be scoped as a dedicated workstream on any net-new system. EHR integration timelines depend heavily on the EHR vendor's sandbox access and API maturity.

## Related Entries
- [Prior Authorization](prior-authorization.md) — common workflow at the payer-provider boundary
- [Patient Identity](patient-identity.md) — the hard problem of matching patients across systems

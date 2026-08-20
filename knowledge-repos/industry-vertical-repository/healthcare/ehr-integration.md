---
id: ehr-integration
vertical: healthcare
tags: [healthcare, ehr, epic, cerner, fhir, smart-on-fhir, interoperability]
surfaces-at: [application-design, functional-design]
related: [healthcare-overview, patient-identity, prior-authorization]
---

# EHR Integration

## What It Is
Electronic Health Record (EHR) integration is the connection between external systems and the clinical systems of record used by healthcare providers — Epic, Oracle Health (Cerner), Athenahealth, and others. EHR integration is required for virtually any digital health, payer-provider interoperability, or care management engagement that involves clinical data from health systems or physician practices.

## Why It Matters in Healthcare
The EHR is where clinical data lives — diagnoses, medications, lab results, imaging, care plans, and encounter notes. Any system that needs to read or write clinical data for a patient being treated at a health system must integrate with the EHR. EHR vendors control this integration surface tightly — both for legitimate data integrity reasons and to protect their platform position. Integration complexity and timeline risk are among the most consistent failure modes in digital health programs.

## Key Concepts
- **Epic**: The dominant EHR in the US — over 35% of US patients have records in Epic. Epic's integration surface includes: FHIR R4 APIs, SMART on FHIR app framework, HL7 v2 interfaces (ADT, ORU, ORM), and the Epic App Orchard for certified third-party apps. Epic environments are called MyChart (patient portal), Hyperspace (clinical workstation), and Beaker (lab).
- **Oracle Health (Cerner)**: The second-largest EHR platform. Cerner's integration surface includes FHIR R4 APIs, HL7 v2, and CDS Hooks. Integration patterns are similar to Epic but with distinct API behaviors and sandbox access processes.
- **SMART on FHIR**: The authorization and launch framework for EHR-embedded apps. Enables a third-party app to launch within the EHR context (knowing the current patient and provider) and access FHIR APIs with OAuth2 tokens scoped to that context. The standard for certified EHR-integrated apps.
- **CDS Hooks**: A standard for EHR-embedded clinical decision support. Hooks fire at defined clinical workflow moments (patient open, order entry, medication prescribe) and call external services that can return suggestions, alerts, or smart forms into the EHR workflow.
- **HL7 v2 Interfaces**: Legacy message-based interfaces still widely used for high-volume clinical events — ADT (admit/discharge/transfer), lab results (ORU), orders (ORM). Delivered via TCP/IP MLLP or VPN file drops. Present in every brownfield health system integration.
- **Epic App Orchard / Cerner Code**: The app marketplaces through which Epic and Cerner certify third-party integrations. Apps must pass review processes (weeks to months) before being available to customer health systems. This is a prerequisite for any Epic-embedded integration at scale.
- **Sandbox Access**: EHR vendors provide sandbox environments for development and testing. Gaining sandbox access (particularly for Epic) requires a formal application process that can take weeks. This is a critical path item that must be initiated at project start.

## Common Patterns / Gotchas
- **Sandbox access is on the critical path.** Epic sandbox access requires a formal application and approval process. Start this before the first sprint. Delaying sandbox access is the most common avoidable schedule risk in EHR integration programs.
- **Each health system has customized their EHR.** Hospitals customize EHR workflows, data fields, and integration configurations extensively. An integration that works on Epic at one health system may behave differently at another. Integration testing must include the specific customer environment.
- **FHIR API coverage is incomplete.** EHR FHIR APIs do not expose all clinical data. Many data elements (structured clinical notes, custom fields, workflow state) are not available via standard FHIR. Validate API coverage against your data requirements before committing to the FHIR-only approach.
- **Write-back is much harder than read.** Reading patient data via FHIR is relatively straightforward. Writing clinical data back into the EHR (creating orders, updating medications, documenting in the chart) requires deeper integration patterns and more rigorous review processes.
- **App Orchard / Cerner Code certification takes months.** If your integration requires Epic or Cerner marketplace listing, build 2–4 months of certification review time into the plan. This timeline is outside your control.

## Industry Insight
🏥 **Industry Insight — EHR Integration**: You're integrating with an EHR. Initiate sandbox access requests (especially Epic) as the first action of the project — this is the most common avoidable schedule risk in digital health. Validate FHIR API coverage against your specific data requirements early; EHR FHIR APIs do not expose all clinical data, and gaps discovered late force architecture changes. SMART on FHIR is the right pattern for EHR-embedded apps; CDS Hooks is the right pattern for clinical decision support. → `industry-vertical-repository/healthcare/ehr-integration.md`

## Solutions Context
**Typical engagement patterns**: Digital health apps with EHR data integration, SMART on FHIR application development, CDS Hooks clinical decision support, payer-provider data exchange, care gap and analytics platforms.

**Common scope anchors**: SMART on FHIR authorization and launch, FHIR R4 resource consumption, CDS Hooks integration, HL7 v2 ADT/ORU processing, Epic App Orchard or Cerner Code certification, sandbox environment setup.

**Risk factors**: Sandbox access timeline is the most common schedule risk. FHIR API coverage gaps discovered mid-project force design changes. App marketplace certification timelines are outside team control and frequently underestimated.

## Related Entries
- [Healthcare Overview](_overview.md)
- [Patient Identity](patient-identity.md)
- [Prior Authorization](prior-authorization.md)

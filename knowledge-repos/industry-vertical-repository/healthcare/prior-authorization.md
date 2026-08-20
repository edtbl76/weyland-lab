---
id: prior-authorization
vertical: healthcare
tags: [healthcare, prior-auth, payer, workflow, fhir, cms]
surfaces-at: [application-design, functional-design]
related: [healthcare-overview, patient-identity]
---

# Prior Authorization

## What It Is
Prior authorization (PA) is the process by which a payer (insurance company) must approve certain procedures, medications, or referrals before a provider delivers them. It is a high-friction, high-volume workflow sitting at the intersection of every provider and every payer — and one of the most targeted areas for automation in healthcare IT.

## Why It Matters in Healthcare
PA is responsible for significant administrative burden on provider staff and meaningful care delays for patients. It is also a major CMS regulatory focus: the 2024 CMS Interoperability and Prior Authorization Rule mandates that payers expose FHIR-based Prior Auth APIs and provide real-time responses for certain request types by 2026–2027. Any system touching PA workflows will need to account for this mandate.

## Key Concepts
- **PA Request**: Initiated by a provider on behalf of a patient. Contains clinical documentation, procedure codes (CPT/HCPCS), diagnosis codes (ICD-10), and patient demographics.
- **Clinical Review**: Payer evaluates the request against clinical criteria (often InterQual or MCG guidelines). Can be automated (auto-approval) or require human review.
- **Approval / Denial / Pend**: Three outcomes. Denials include a reason code and appeal rights. Pend means more information is needed.
- **Gold Carding**: An exception process where high-performing providers are exempt from PA requirements for specific procedures. Increasingly mandated by state law.
- **Real-Time PA (RTPA)**: CMS-mandated capability for payers to respond to PA requests in real-time via FHIR APIs for certain procedure types. Changes the latency profile from days to seconds.
- **X12 278**: The EDI standard for PA requests and responses. Still widely used by payers; FHIR Prior Auth IG is the emerging standard.
- **FHIR Prior Auth IG**: The HL7 FHIR Implementation Guide for prior authorization. Built on CDS Hooks and the Da Vinci project. This is the direction CMS mandates are pushing.

## Common Patterns / Gotchas
- **Model PA as a state machine from day one.** States: draft → submitted → pending → approved / denied / partially-approved / cancelled. Trying to retrofit state tracking onto a non-state-machine model causes significant pain.
- **Payer variations are significant.** Each payer has its own rules, turnaround times, clinical criteria, and integration quirks. A system serving multiple payers needs a payer configuration layer, not hardcoded logic.
- **Turnaround time requirements are regulatory.** CMS mandates 72 hours for non-urgent, 24 hours for urgent (expedited) PA decisions. State laws may be stricter. These are SLA requirements, not aspirations.
- **Attachments are the hard part.** Clinical documentation (PDFs, CDA documents, images) must be transmitted alongside the PA request. File handling, storage, and retrieval add significant scope.
- **Appeals are in scope.** Denials have appeal rights. If you're building a PA platform, appeals workflow is not optional.

## Industry Insight
🏥 **Industry Insight — Prior Authorization**: You're designing a prior authorization system. Model the PA lifecycle as an explicit state machine before writing any code — the states (draft, submitted, pending, approved, denied, appealed) are regulatory, not optional. Each payer has its own rules and integration requirements; design a payer configuration layer rather than hardcoding payer logic. CMS RTPA mandates will require FHIR Prior Auth API support for applicable payers by 2026. → `industry-vertical-repository/healthcare/prior-authorization.md`

## Solutions Context
**Typical engagement patterns**: PA automation platforms for provider groups or health systems; payer PA workflow modernization; interoperability compliance work (CMS rule readiness).

**Common scope anchors**: State machine design, payer integration layer, FHIR Prior Auth IG implementation, X12 278 support, clinical attachment handling, appeals workflow, reporting and audit trail.

**Risk factors**: Payer-specific variations significantly increase integration scope. Clinical attachment handling (PDF, CDA) is frequently underscoped. CMS mandate timelines create hard compliance deadlines that may drive prioritization.

**Estimation notes**: A greenfield PA platform with 2–3 payer integrations is a substantial engagement. Each payer integration should be scoped individually. RTPA (real-time) adds meaningful complexity over async/batch PA.

## Related Entries
- [Healthcare Overview](_overview.md) — regulatory and integration landscape
- [Patient Identity](patient-identity.md) — patient matching is required before PA submission

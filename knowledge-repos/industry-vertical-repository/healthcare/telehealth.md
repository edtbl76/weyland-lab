---
id: telehealth
vertical: healthcare
tags: [healthcare, telehealth, virtual-care, video-visit, remote-monitoring, hipaa]
surfaces-at: [application-design, functional-design]
related: [healthcare-overview, ehr-integration, patient-identity]
---

# Telehealth

## What It Is
Telehealth is the delivery of healthcare services through digital channels — synchronous video visits, asynchronous messaging, remote patient monitoring (RPM), and digital therapeutics. It spans direct-to-consumer telehealth platforms (where patients connect with providers outside a traditional health system), health system-integrated virtual care (where a patient's own provider delivers care remotely), and remote monitoring programs for chronic disease management.

## Why It Matters in Healthcare
Telehealth expanded dramatically during COVID-19 and has maintained a significant share of outpatient visits — particularly for behavioral health, primary care, and chronic disease follow-up. For health systems, virtual care extends reach, improves access for rural and underserved populations, and reduces no-show rates. For payers, telehealth is a cost management lever for appropriate-care-setting navigation. Regulatory flexibilities granted during the pandemic are being codified into permanent law, stabilizing the compliance landscape.

## Key Concepts
- **Synchronous Video Visit**: Real-time video consultation between patient and provider. The core telehealth modality. HIPAA requires BAA with the video platform vendor; consumer video tools (Zoom standard, FaceTime) are not compliant without a BAA. HIPAA-compliant platforms: Zoom for Healthcare, Doxy.me, Teladoc, Amwell.
- **Asynchronous / Store-and-Forward**: Patient submits clinical information (photos, symptom questionnaire, records) for provider review without a real-time interaction. Common for dermatology, ophthalmology, and some primary care use cases.
- **RPM (Remote Patient Monitoring)**: Continuous or periodic collection of physiological data from patients at home — blood pressure, glucose, weight, SpO2, ECG. Data flows from connected devices to a clinical monitoring platform. Reimbursed by Medicare under CPT codes 99453/99454/99457/99458.
- **Ryan Haight Act**: Federal law requiring an in-person evaluation before prescribing controlled substances via telemedicine. COVID-era DEA flexibilities allowed prescribing without in-person visit; permanent rules are being finalized. Any telehealth platform supporting behavioral health or pain management must account for prescribing restrictions.
- **State Licensure**: Providers must be licensed in the state where the patient is located at the time of the visit — not where the provider practices. Multi-state telehealth platforms require provider licensure tracking and enforcement. The Interstate Medical Licensure Compact (IMLC) simplifies multi-state licensure for participating states.
- **Parity Laws**: Many states require payers to reimburse telehealth visits at the same rate as in-person visits. Parity requirements vary by state and payer type (commercial, Medicaid, Medicare). The platform must support documentation sufficient for telehealth billing codes.
- **Virtual Waiting Room**: The patient-facing queue management experience before a video visit — check-in, consent, intake forms, insurance verification. First impressions of the platform are formed here.
- **Device and Bandwidth Considerations**: Telehealth platforms must perform on low-bandwidth connections and older devices, particularly for rural and elderly populations. Adaptive video quality, low-bandwidth fallback modes, and phone-only options are accessibility requirements.

## Common Patterns / Gotchas
- **HIPAA compliance is non-negotiable and vendor-dependent.** BAAs are required with every vendor in the video stack. Cloud recording of visits requires explicit patient consent and secure storage. Do not assume standard consumer video platforms are compliant.
- **EHR integration is the adoption lever.** Telehealth platforms that require providers to work outside their EHR workflow face adoption resistance. Integration with Epic, Cerner, and Athena (launching from within the EHR, auto-documenting the visit) is a key success factor for health system deployments.
- **State licensure enforcement is an operational requirement.** The platform must check provider licensure against the patient's state at the time of visit booking and prevent visits where coverage is not established. This requires maintaining current licensure data for all providers — an ongoing operational burden.
- **RPM reimbursement requires documentation rigor.** Medicare RPM codes have specific requirements — device setup, 16+ days of data per 30-day period, clinical review time. The platform must generate compliant documentation automatically; manual documentation at scale is not viable.
- **Behavioral health has distinct privacy rules.** 42 CFR Part 2 governs substance use disorder treatment records — stricter than standard HIPAA. Behavioral health telehealth platforms must implement Part 2-compliant consent and disclosure controls.

## Industry Insight
🏥 **Industry Insight — Telehealth**: You're designing a telehealth platform. HIPAA compliance requires BAAs with every vendor in the video and data stack — audit all third-party dependencies before architecture is finalized. EHR integration (launching from within Epic or Cerner, auto-populating the note) is the single most important adoption factor for health system deployments; design it as a core feature, not an integration. State licensure enforcement must be automated — manual licensure checking does not scale across large provider panels. → `industry-vertical-repository/healthcare/telehealth.md`

## Solutions Context
**Typical engagement patterns**: Direct-to-consumer telehealth platform, health system virtual care integration, remote patient monitoring program, behavioral health telehealth, telehealth platform white-labeling.

**Common scope anchors**: HIPAA-compliant video infrastructure, EHR integration (Epic/Cerner launch and documentation), virtual waiting room and intake, state licensure enforcement, RPM device integration and data pipeline, billing documentation for telehealth codes.

**Risk factors**: State licensure tracking is an ongoing operational obligation — provider licensure changes require real-time system updates. Ryan Haight / DEA controlled substance prescribing rules are in flux; build compliance as a configurable rule, not hardcoded logic. RPM reimbursement documentation requirements are strict and require careful workflow design.

## Related Entries
- [Healthcare Overview](_overview.md)
- [EHR Integration](ehr-integration.md)
- [Patient Identity](patient-identity.md)

---
id: care-management
vertical: healthcare
tags: [healthcare, care-management, population-health, chronic-disease, care-coordination]
surfaces-at: [application-design, functional-design]
related: [healthcare-overview, patient-identity, ehr-integration, prior-authorization]
---

# Care Management

## What It Is
Care management is the coordinated set of activities, workflows, and technology that supports proactive management of patients with chronic conditions, high utilization, or complex care needs. It spans population health management (identifying and stratifying at-risk patients), care coordination (connecting patients with appropriate services), case management (intensive support for complex patients), and disease management programs (structured interventions for specific conditions like diabetes, CHF, or COPD). It is practiced by health systems, payers, ACOs, and value-based care organizations.

## Why It Matters in Healthcare
The US healthcare system's shift from fee-for-service to value-based care (where providers are paid for outcomes, not volume) has made care management a financial imperative. 5% of patients account for roughly 50% of healthcare costs — identifying and actively managing this population reduces avoidable hospitalizations, ER visits, and readmissions. CMS quality programs (HEDIS, Stars, ACO REACH) measure care gap closure and preventive care rates, with financial consequences. Care management technology is the operational infrastructure for these programs.

## Key Concepts
- **Population Health Management**: Analytics and workflow tools for identifying, stratifying, and managing patient populations at scale. Requires aggregating clinical data across EHRs, claims, labs, and social determinants to build a complete patient picture.
- **Risk Stratification**: Scoring patients by their likelihood of high-cost utilization or adverse outcomes. Used to prioritize care management outreach — who needs intensive intervention vs routine monitoring. Models range from simple HCC-based scoring to ML-based predictive models.
- **Care Gap**: A preventive or chronic care service that a patient is due for but has not received — annual wellness visit, A1C test, mammogram, colorectal screening. Closing care gaps is a primary HEDIS and Stars quality measure.
- **Care Plan**: A documented plan of care goals, interventions, and responsibilities for a specific patient. In care management platforms, care plans are structured, longitudinal, and shared across the care team.
- **Care Coordinator / Case Manager**: The clinical staff role that manages patient outreach, care plan execution, and cross-provider coordination. Care management platforms must support their workflows — patient lists, task management, communication, and documentation.
- **Transitions of Care (ToC)**: The handoffs between care settings — hospital discharge to home, SNF to home, ED visit follow-up. Transition failures are a leading cause of readmissions. ToC management programs target these high-risk moments.
- **SDOH (Social Determinants of Health)**: Non-clinical factors affecting health outcomes — housing stability, food security, transportation, financial stress. Increasingly captured in care management platforms and used for risk stratification and referral to community resources.
- **HL7 FHIR / CDA for Care Plans**: FHIR CarePlan and ClinicalImpression resources are the standards for structured care plan exchange. C-CDA (Consolidated CDA) is the legacy format used for care transitions documents.
- **ACO (Accountable Care Organization)**: A group of providers jointly responsible for the cost and quality of care for a defined population under value-based contracts. ACOs require population health and care management infrastructure.

## Common Patterns / Gotchas
- **Data aggregation is the hard problem, not workflow.** A care management platform is only as good as its patient data. Aggregating clinical data from multiple EHRs, claims feeds, lab systems, and remote monitoring devices is the primary technical challenge — and it is never complete.
- **Risk stratification models require validation and recalibration.** A model trained on one population may not perform on another. Stratification models must be validated against actual outcomes and recalibrated regularly. Poorly calibrated models waste care coordinator time on low-risk patients.
- **Care coordinator workflow design determines adoption.** Care coordinators manage large patient panels. Platforms that require excessive clicks, don't surface the right information at the right time, or don't fit into existing workflows will not be adopted regardless of data quality.
- **Patient outreach is operationally complex.** Reaching patients for care gap closure requires multi-channel outreach (phone, text, patient portal message), tracking response rates, and escalating non-responders. Outreach workflow is a significant operational design area.
- **Attribution is a recurring pain point.** In value-based contracts, "which patients are in my population?" is determined by attribution methodology — which patients are attributed to which provider based on claims, assignment, or enrollment. Attribution changes frequently and is often disputed.

## Industry Insight
🏥 **Industry Insight — Care Management**: You're designing a care management platform. Data aggregation across EHRs and claims is the foundational technical challenge — invest in the data integration layer before the care management workflow, because workflows operating on incomplete data produce poor outcomes regardless of UX quality. Risk stratification models require ongoing validation against actual outcomes; treat model governance as an operational function, not a one-time calibration. Care coordinator workflow must be designed with care coordinators, not for them — adoption is the primary delivery risk. → `industry-vertical-repository/healthcare/care-management.md`

## Solutions Context
**Typical engagement patterns**: Population health management platform, ACO care management infrastructure, chronic disease management programs, transitions of care management, HEDIS/Stars quality improvement, SDOH integration.

**Common scope anchors**: Multi-source data aggregation (EHR, claims, labs, remote monitoring), risk stratification model, care gap identification and tracking, care plan management, care coordinator workflow, patient outreach, FHIR CarePlan integration.

**Risk factors**: EHR data feed quality and coverage vary significantly across provider organizations — data completeness is an ongoing operational challenge. Risk model accuracy requires outcome data for validation. Care coordinator adoption is the primary program success risk and requires change management investment.

## Related Entries
- [Healthcare Overview](_overview.md)
- [Patient Identity](patient-identity.md)
- [EHR Integration](ehr-integration.md)
- [Prior Authorization](prior-authorization.md)

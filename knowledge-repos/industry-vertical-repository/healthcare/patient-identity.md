---
id: patient-identity
vertical: healthcare
tags: [healthcare, identity, mpi, matching, hipaa, interoperability]
surfaces-at: [requirements-analysis, application-design, functional-design]
related: [healthcare-overview, prior-authorization]
---

# Patient Identity

## What It Is
Patient identity is the problem of uniquely identifying and correctly matching a patient across systems, organizations, and encounters. The US has no universal patient identifier — every hospital, payer, and clinic assigns its own. Matching patients correctly across these systems is foundational to interoperability, continuity of care, and safe clinical decisions.

## Why It Matters in Healthcare
A wrong match — merging two different patients' records — can result in a patient receiving the wrong treatment based on another patient's history. An under-match — treating the same patient as two different people — fragments their record and degrades care quality. Both are patient safety issues, not just data quality issues. Any system that aggregates or exchanges patient data across organizations must have a deliberate identity strategy.

## Key Concepts
- **MPI (Master Patient Index)**: A central registry that maintains a single authoritative record per patient with links to their identities across source systems. The backbone of patient identity management.
- **EMPI (Enterprise MPI)**: An MPI that spans multiple organizations or facilities. Common in health systems and HIEs.
- **Deterministic Matching**: Exact-match rules using identifiers like SSN, MRN, or date of birth + name. Fast and precise but brittle — a typo breaks a match.
- **Probabilistic Matching**: Scoring algorithms that weight multiple attributes to determine match likelihood. More resilient to data quality issues but produces a match confidence score that requires threshold decisions.
- **Referential Matching**: Matching against a reference database (e.g., a national identity dataset) rather than just internal records. Higher accuracy, third-party dependency.
- **Golden Record**: The authoritative, deduplicated view of a patient synthesized from matched source records.
- **Match / No Match / Possible Match**: The three outcomes of identity resolution. "Possible match" requires human review — this queue must be managed.

## Common Patterns / Gotchas
- **Define your match threshold policy before writing code.** The precision/recall tradeoff (false positives vs false negatives) is a clinical and policy decision, not a technical one. Teams that defer this create systems with hidden, untuned behavior.
- **Data quality in source systems is poor.** Name variations, date of birth errors, multiple SSNs, and address inconsistencies are common. The matching algorithm must be resilient; the data cannot be assumed clean.
- **Merging is easier than unmerging.** Incorrectly merged records are very difficult to separate after the fact. Design the unmerge/split workflow explicitly and test it.
- **HIPAA governs the identity data.** SSN, date of birth, address, and name are all PHI. Identity infrastructure carries full HIPAA obligations.
- **FHIR Patient resource is the exchange format.** When sharing identity across systems, use the FHIR Patient resource. The `identifier` array carries MRNs, insurance IDs, and other system-specific identifiers alongside the patient's demographics.

## Industry Insight
🏥 **Industry Insight — Patient Identity**: You're building a system that handles patient data across sources. Establish your identity resolution strategy before designing data models — whether deterministic, probabilistic, or referential matching, and what your false-positive/false-negative threshold will be. This is a clinical policy decision, not just a technical one. Plan explicitly for the "possible match" review queue and the unmerge workflow; both are frequently underscoped. → `industry-vertical-repository/healthcare/patient-identity.md`

## Solutions Context
**Typical engagement patterns**: Health system interoperability platforms, HIE infrastructure, payer-provider data exchange, patient portal consolidation across acquired facilities.

**Common scope anchors**: MPI/EMPI design, matching algorithm selection and tuning, golden record strategy, possible-match review workflow, FHIR Patient resource integration, unmerge capability.

**Risk factors**: Matching algorithm tuning requires real patient data for validation — this has HIPAA and timeline implications. Source system data quality is almost always worse than expected. Unmerge is frequently deprioritized and becomes a production incident later.

**Estimation notes**: A standalone MPI implementation is a significant workstream. Probabilistic matching tuning should be scoped as an iterative process, not a one-time task. Integration with each source system (EHR, payer system) should be scoped separately.

## Related Entries
- [Healthcare Overview](_overview.md) — regulatory and integration landscape
- [Prior Authorization](prior-authorization.md) — patient identity is a prerequisite for PA submission

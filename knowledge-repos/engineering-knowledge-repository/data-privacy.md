---
id: data-privacy
tags: [methodology, security, data, backend]
surfaces-at: [application-design, functional-design, requirements-analysis]
related: [encryption, data-lineage, audit-logging, data-contracts, rbac]
complexity: intermediate
---

# Data Privacy

## What It Is
The engineering practices for handling personal data in compliance with privacy regulations and user expectations — including how data is collected, stored, accessed, retained, and deleted. GDPR (Europe), CCPA (California), HIPAA (healthcare), and PCI-DSS (payment data) define legal obligations. Beyond compliance, data privacy is a trust contract with users: their data is handled only for its stated purpose, protected from unauthorized access, and deleted when they ask. For consulting firms building client products, privacy engineering is often a compliance requirement and a contractual obligation.

## When to Apply
- Any application handling personal data (name, email, location, health, financial data)
- Applications with EU, California, or other regulated-jurisdiction users (GDPR, CCPA)
- Healthcare (HIPAA), payment (PCI), or government (FedRAMP) contexts
- Any data pipeline that processes or stores user-identifiable information

## Key Concepts
- **PII (Personally Identifiable Information)**: Data that can identify an individual directly or indirectly — name, email, phone, IP address, device ID, location, biometrics, health data. Treat all PII with heightened care: minimize collection, limit access, encrypt storage, and enable deletion
- **Data Minimization**: Collect only the data you need for the stated purpose. Don't collect a user's date of birth if you only need to verify they are 18+ — collect an age verification boolean instead. Data you don't collect cannot be breached
- **Purpose Limitation**: Use data only for the purpose it was collected. If email was collected for transactional notifications, don't use it for marketing without explicit additional consent
- **Consent Management**: Under GDPR, most personal data processing requires a legal basis — consent, contractual necessity, legitimate interest, or legal obligation. Consent must be freely given, specific, informed, and unambiguous. Implement consent collection with a Consent Management Platform (OneTrust, Cookiebot)
- **Right to Access (SAR — Subject Access Request)**: Users can request a copy of all their personal data. Systems must be able to export all data for a given user across all datastores. This requires knowing where all user data lives — see [Data Lineage](data-lineage.md)
- **Right to Erasure ("Right to be Forgotten")**: Users can request deletion of their personal data. Systems must be able to delete or anonymize all data for a given user. Complications: data in backups, audit logs, and analytics systems. Define a deletion policy that handles each data store
- **Data Anonymization vs. Pseudonymization**:
  - *Anonymization*: Irreversibly removes identifying information. Anonymized data is no longer PII under GDPR. Hard to achieve truly; k-anonymity is a common standard
  - *Pseudonymization*: Replace identifiers with pseudonyms (user_id instead of email). Data is still PII but has reduced re-identification risk. The most practical approach for analytics and data warehouses
- **Access Control for Personal Data**: Apply least-privilege to PII. Application service accounts should have column-level access only to the PII they need. Analysts querying user data should see pseudonymized data unless they have a specific role. Row-level security in the database can enforce per-team data access
- **Data Retention Policies**: Define how long each category of data is retained. Transaction records: 7 years (tax). Marketing preferences: until opt-out. Session logs: 90 days. Delete or anonymize data at the end of its retention period. Automated deletion is more reliable than manual
- **Privacy by Design**: Incorporate privacy requirements into the design phase, not as an afterthought. Privacy impact assessments (PIAs/DPIAs) for new features handling sensitive data. Build deletion, access, and export capabilities into the data model from the start
- **Data Breach Response**: GDPR requires notifying supervisory authorities within 72 hours of discovering a breach affecting personal data. Have a response plan: detect, contain, assess, notify. Maintain an incident log

## In Practice
Method conducts DPIA (Data Protection Impact Assessment) for any new feature handling personal data. PII columns are encrypted at rest using column-level encryption via KMS. Data is pseudonymized before loading into analytics systems. User deletion requests trigger a deletion pipeline that processes all datastores within 30 days. Consent is managed via OneTrust; consent records are stored with timestamps and versions. Data lineage via DataHub maps PII flows for GDPR compliance reporting.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Data Privacy**: Privacy is easier to build in than to retrofit. Before collecting any new personal data, ask: do we need this? For how long? Who needs access? What happens when users ask for deletion? GDPR's 72-hour breach notification requirement means you need incident detection before you need an incident response plan. Data minimization is the best privacy control — data you don't collect cannot be breached or subpoenaed. Build user deletion as a first-class system capability, not a one-off script — it will be needed repeatedly. Pseudonymize data in analytics pipelines by default; make re-identification a deliberate, audited action. → `engineering-knowledge-repository/data-privacy.md`

## Related Entries
- [Encryption](encryption.md) — encryption at rest and in transit is the primary technical control for personal data protection
- [Data Lineage](data-lineage.md) — lineage enables answering "where does this user's data live?" for access and deletion requests
- [Audit Logging](audit-logging.md) — audit logs provide the evidence trail for compliance and breach investigations
- [Data Contracts](data-contracts.md) — data contracts can encode privacy classifications and handling requirements for PII fields
- [RBAC](rbac.md) — role-based access control limits who can access personal data to those with a legitimate need

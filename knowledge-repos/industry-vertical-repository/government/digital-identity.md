---
id: digital-identity-government
vertical: government
tags: [government, identity, authentication, login.gov, piv, cac, proofing, mfa]
surfaces-at: [application-design, functional-design]
related: [government-overview, case-management-government]
---

# Digital Identity (Government)

## What It Is
Digital identity in government encompasses the systems and processes for verifying who a citizen or employee is, authenticating their access to government services, and managing their credentials across multiple agencies and programs. It spans identity proofing (verifying that a person is who they claim to be), authentication (verifying identity at each access), and federation (enabling a single identity to be used across multiple government systems). For federal employees and contractors, it includes PIV/CAC card-based authentication for physical and logical access.

## Why It Matters in Government
Government digital services are only valuable if citizens can reliably access them — and only secure if access is controlled to the right people. Identity is the foundation of every government digital service. Weak identity proofing enables fraud (improper benefits claims, fraudulent tax refunds). Cumbersome authentication drives citizens away from digital channels and back to paper. For federal systems, strong authentication is a mandatory NIST and OMB requirement, not optional.

## Key Concepts
- **Identity Proofing**: The process of verifying that an individual is who they claim to be at enrollment. NIST SP 800-63A defines three Identity Assurance Levels (IAL1-3) with progressively stronger proofing requirements. IAL2 (required for most government benefit programs) requires document verification and either in-person or supervised remote proofing.
- **Authentication Assurance Level (AAL)**: NIST SP 800-63B defines three AALs for authentication strength. AAL2 (required for most government systems with personal data) requires multi-factor authentication. AAL3 requires hardware-based MFA (PIV/CAC or FIDO2 hardware key).
- **PIV (Personal Identity Verification)**: The federal government's smart card standard (FIPS 201) for employee and contractor physical and logical access. PIV cards contain a certificate for digital signature, authentication, and encryption. All federal systems must support PIV authentication for employees.
- **CAC (Common Access Card)**: The DoD equivalent of PIV. Same standard, different issuing authority.
- **login.gov**: The US federal government's shared identity platform — a single sign-on service that allows citizens to use one credential across multiple federal agencies. Agencies are OMB-directed to use login.gov rather than building their own identity systems. login.gov provides IAL1 and IAL2 proofing and AAL2 authentication.
- **FICAM (Federal Identity, Credential, and Access Management)**: The federal framework governing identity, credential, and access management across the federal government. FICAM architecture and trust frameworks govern how agencies federate identities.
- **Federation / SAML / OIDC**: The protocols by which identity assertions are shared across systems. SAML 2.0 is the legacy federal standard; OpenID Connect (OIDC) is the modern standard. login.gov uses OIDC. Agency applications must implement the federation protocol to accept login.gov or other IdP assertions.
- **MFA (Multi-Factor Authentication)**: Required at AAL2 — something you know (password) + something you have (authenticator app, SMS OTP, hardware key) or something you are (biometric). SMS OTP is deprecated by NIST for high-assurance applications due to SIM-swap vulnerability.
- **Remote Identity Proofing**: IAL2 proofing without in-person verification — using document scanning (driver's license, passport), facial comparison against the document photo, and liveness detection to prevent spoofing. Requires vendor integration (IDEMIA, Jumio, ID.me, Socure).

## Common Patterns / Gotchas
- **Use login.gov for citizen-facing federal applications.** OMB M-19-17 directs agencies to use shared identity services (login.gov, max.gov) rather than building agency-specific identity platforms. A new federal citizen portal that builds its own identity system faces OMB compliance questions.
- **IAL2 proofing dropout rates are significant.** Remote identity proofing (document scan + facial comparison) has dropout rates of 20–50% — due to poor document quality, camera limitations, and user friction. Design for proofing failures with graceful fallback (supervised video proofing, in-person alternatives) rather than treating proofing as always-successful.
- **PIV integration requires PKI infrastructure.** Accepting PIV card authentication requires validating the PIV certificate against the issuing CA and checking the certificate revocation list (CRL). This requires PKI integration that is not trivial to implement and must be maintained as certificates are renewed.
- **Equity and accessibility in identity proofing is a policy concern.** Identity proofing methods that require a smartphone, good lighting, or specific document types can exclude populations (elderly, unhoused, populations without government ID) from accessing benefits they are entitled to. Alternative proofing pathways are often a program requirement.
- **Session management must balance security and usability.** Aggressive session timeouts (required by security policy) frustrate citizens completing complex multi-step applications. Implement secure session resumption (save progress) so session expiry doesn't force citizens to restart lengthy applications.

## Industry Insight
🏛️ **Industry Insight — Government Digital Identity**: You're designing authentication for a government system. Use login.gov for federal citizen-facing applications — OMB direction and existing investment make it the right default for new federal systems. Design for IAL2 proofing dropout rates of 20–50% with graceful fallback pathways; proofing failures are not edge cases. PIV/CAC authentication for federal employees requires PKI integration and certificate validation infrastructure — validate this integration complexity early. Equity in identity proofing (alternative pathways for citizens without smartphones or specific document types) is often a program requirement, not a nice-to-have. → `industry-vertical-repository/government/digital-identity.md`

## Solutions Context
**Typical engagement patterns**: Citizen identity and authentication (login.gov integration), PIV/CAC enterprise SSO, identity proofing platform, MFA implementation for federal systems, ICAM modernization.

**Common scope anchors**: login.gov or IdP integration (OIDC/SAML), IAL2 identity proofing workflow and vendor integration, MFA implementation (authenticator app, FIDO2), PIV/CAC certificate validation, session management, alternative proofing pathways.

**Risk factors**: IAL2 proofing dropout rates are higher than expected — plan for fallback pathways from the start. PIV PKI infrastructure complexity is consistently underestimated. login.gov integration timeline depends on GSA agency onboarding queue, which is outside team control.

## Related Entries
- [Government Overview](_overview.md)
- [Case Management](case-management.md)

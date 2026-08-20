---
id: defense-in-depth
tags: [principle, security]
surfaces-at: [nfr-requirements, nfr-design]
related: [zero-trust-security, principle-of-least-privilege, owasp-top-ten, secrets-management]
complexity: foundational
---

# Defense in Depth

## What It Is
A security strategy that applies multiple independent layers of security controls so that if one layer fails, others remain effective. Originally a military concept. The principle: no single security control is perfect; when controls are layered, an attacker must defeat all of them. Controls operate at different levels — network, application, data, host, perimeter — creating overlapping protection.

## When to Apply
- All production systems — defense in depth is a universal security principle
- When designing threat models — identify which controls cover each attack vector, verify no single control is the sole defense
- When a security control change is proposed — assess what other controls back it up
- Security reviews and audits — defense in depth is the framework for evaluating completeness

## When Not to Apply
- Layering cannot substitute for fundamentally broken controls. Defense in depth means layers back each other up — not that weak controls are acceptable because something else will catch it.

## Key Concepts
- **Layers**: Network (firewall, WAF), Host (OS hardening, endpoint protection), Application (input validation, auth), Data (encryption at rest and in transit), Identity (MFA, least privilege)
- **Independent Controls**: Each layer should be independently effective — a failure in layer 1 should not compromise layers 2+
- **Redundant Controls**: The same threat is defended against by multiple controls — network-level blocking AND application-level input validation both defend against injection attacks
- **Attack Surface Reduction**: Minimize the surface area attackers can reach — fewer services exposed, fewer permissions granted, fewer entry points
- **Fail Secure**: When a security control fails, it should fail in the secure direction — deny access by default, not allow

## In Practice
Defense in depth is the framing method for security architecture reviews in Method engagements. The checklist: Is traffic encrypted in transit? Is data encrypted at rest? Are inputs validated at every layer? Is access controlled at network AND application level? Is authentication required AND authorization enforced? Each "yes" is a layer; each "no" is a gap.

## Engineering Knowledge
💡 **Engineering Knowledge — Defense in Depth**: Security controls fail. Build multiple independent layers so one failure doesn't compromise everything. Network controls AND application controls AND data controls — not either/or. An attacker who bypasses your WAF should still hit input validation; one who bypasses input validation should still encounter parameterized queries. No security architecture with a single critical control is acceptably secure. → `engineering-knowledge-repository/security/defense-in-depth.md`

## Related Entries
- [Zero Trust Security](zero-trust-security.md) — zero trust is defense in depth applied to network and identity security
- [OWASP Top Ten](owasp-top-ten.md) — the common vulnerability classes that defense-in-depth layers must cover
- [Principle of Least Privilege](principle-of-least-privilege.md) — least privilege is one of the key layers in defense in depth

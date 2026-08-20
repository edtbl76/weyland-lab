---
id: core-domain-chart
tags: [ddd, strategy, organizational, architecture]
surfaces-at: [validated-intent, requirements-analysis, application-design]
related: [domain-storytelling, domain-message-flow-modelling, event-storming, wardley-mapping, team-topologies, build-buy-partner, independent-service-heuristics]
complexity: intermediate
---

# Core Domain Chart

## What It Is
A strategic Domain-Driven Design tool for classifying an organization's software domains into three categories — Core, Supporting, and Generic — based on their competitive value. Introduced by Eric Evans and expanded by Nick Tune in *Architecture Modernization*. The chart makes explicit where a company's investment, talent, and attention should be concentrated, and where it should be minimized or outsourced. It is the starting point for modernization prioritization: you cannot make good architectural decisions without knowing which parts of the system are strategically differentiated and which are not.

## When to Use
- At the start of an architecture modernization engagement to establish investment priorities
- When a client is asking "where should we focus?" or "what should we build vs. buy?"
- When teams are spread thin across too many domains without clear prioritization
- To justify outsourcing or using off-the-shelf solutions for non-core domains
- During org design discussions — team investment should mirror domain investment
- When there is disagreement between business and engineering about what matters most

## Key Concepts
- **Core Domain**: The domain that directly delivers competitive advantage — what the business does that no one else does as well. This is where the best engineers, the most investment, and the most design care should go. Examples: recommendation engine for a streaming platform, underwriting model for an insurer, routing algorithm for a logistics company. A company typically has only one or two true Core Domains.
- **Supporting Subdomain**: Necessary for the business to operate, but not a source of competitive advantage. Worth building in-house if it is tightly coupled to the Core, but should not be over-engineered. Custom-built, but not obsessed over. Example: internal reporting tool, employee onboarding system.
- **Generic Subdomain**: Commodity functionality that is well-solved by the market. Should almost always be bought, licensed, or replaced with a SaaS product rather than built. Investment here destroys value. Examples: authentication, billing, email delivery, CMS.
- **The classification is strategic, not technical**: A piece of software is not Generic because it is simple. It is Generic because the market has already solved it well enough. The question is not "is this hard?" but "does building this ourselves create competitive advantage?"
- **Misclassification is the common failure**: Organizations routinely treat Generic domains as Core (over-investing in commodity problems) and under-invest in their actual Core Domain. The Core Domain Chart makes this visible and creates accountability for the mismatch.
- **Core Domains evolve**: A domain that is Core today may become Generic as the market catches up. The chart should be revisited, not treated as permanent.

## Method Application
Core Domain Chart is most valuable at the start of a modernization engagement and during Requirements Analysis when scope decisions are being made. Use it to challenge scope: if a client wants to build something in-house that is clearly Generic, the chart provides the vocabulary and logic to redirect toward buy or integrate. It also informs staffing — Core Domains warrant senior, deeply embedded engineers; Generic Domains do not.

## Consulting Insight
🎯 **Consulting Tool — Core Domain Chart**: The most common modernization mistake is treating every system as equally important. A Core Domain Chart forces the prioritization conversation: what does this company do that creates competitive advantage, and is that reflected in where engineering investment goes? When a client has their best team maintaining a homegrown authentication system while their actual differentiator runs on legacy code nobody wants to touch, the Core Domain Chart is the tool that names that problem. → `consulting-tools-repository/core-domain-chart.md`

## Solutions Context
The Core Domain Chart is a powerful pre-sales and scoping tool. During technical assessments (Tangible Discovery) or discovery conversations, asking "what is your Core Domain?" often reveals misalignment between what the business believes is differentiating and what the system actually reflects. Modernization engagements scoped without this question frequently expand in unexpected directions when the team discovers the client's actual Core Domain is buried under years of Generic domain investment.

## Related Entries
- [Domain Storytelling](domain-storytelling.md) — collaborative technique for surfacing domain knowledge before chart classification
- [Domain Message Flow Modelling](domain-message-flow-modelling.md) — visualizes how classified domains interact
- [Event Storming](event-storming.md) — explores domain complexity; findings inform Core vs. Supporting vs. Generic classification
- [Wardley Mapping](wardley-mapping.md) — complementary strategic view; commodity components on a Wardley Map map to Generic Subdomains
- [Team Topologies](team-topologies.md) — team structure should mirror domain classification; Core Domains warrant stream-aligned teams, Generic Domains may be platform or outsourced
- [Build / Buy / Partner](build-buy-partner.md) — the Core Domain Chart is the primary input to this decision framework
- [Independent Service Heuristics](independent-service-heuristics.md) — validates whether Core Domain candidates can be operated as genuinely independent services before committing to service boundaries

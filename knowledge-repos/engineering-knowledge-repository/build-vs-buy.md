---
id: build-vs-buy
tags: [principle, cost, team-practices]
surfaces-at: [requirements-analysis, application-design]
related: [managed-services-tradeoffs, finops, technical-debt-management]
complexity: intermediate
---

# Build vs. Buy

## What It Is
A decision framework for determining whether to build a capability in-house or purchase/license an existing solution (SaaS, open-source, managed service). Build vs. buy is one of the highest-stakes decisions in software engineering — getting it wrong wastes significant engineering time building undifferentiated infrastructure, or locks a product into an inflexible vendor dependency. The correct answer depends on whether the capability is a core differentiator, the cost and effort of building, the maturity of available solutions, and the long-term ownership cost.

## When to Apply
- Evaluating any new capability the product needs: authentication, search, payments, notifications, analytics, ML infrastructure
- Early in project planning — build vs. buy decisions shape architecture and resourcing
- When an existing in-house solution is becoming a maintenance burden

## Key Concepts
- **The Core Question**: Is this capability a competitive differentiator? If yes, build — owning the capability is strategic. If no, buy — building undifferentiated infrastructure is waste
- **Total Cost of Ownership (TCO)**: Build cost includes initial development, ongoing maintenance, scaling, security patching, and opportunity cost (engineering time not spent on product). Buy cost includes licensing, vendor lock-in risk, integration effort, and potential future migration. TCO over 3-5 years is the right comparison unit — not upfront cost
- **Build Arguments**:
  - Core to competitive advantage or IP
  - No adequate commercial solution exists
  - Unique requirements that commercial solutions can't meet
  - Data sensitivity or compliance prevents third-party handling
  - Long-term cost of licensing exceeds build + maintain cost
- **Buy Arguments**:
  - Commodity capability with mature solutions (auth, payments, email, search)
  - Faster time to market
  - Vendor provides security, compliance, and reliability as a service
  - Engineering team lacks domain expertise
  - Maintenance burden would distract from core product
- **Open Source Middle Ground**: Use open source when a commercial solution is too expensive or inflexible, but building from scratch is wasteful. Open source gives the flexibility of build with much of the speed of buy — at the cost of self-hosting and maintenance
- **Avoid NIH (Not Invented Here)**: Bias toward building because it's "more interesting" or "we can do it better" is a common and expensive mistake. Default to buy for commodity capabilities; reserve engineering effort for differentiated work
- **Vendor Lock-In Risk**: Evaluate exit costs before committing. Can you migrate? Is data exportable? Is the vendor financially stable? Abstract vendor integrations behind interfaces to reduce switching cost
- **The Hybrid**: Buy for the commodity layer; build for the differentiated layer on top. Use Stripe for payments processing; build your subscription management logic. Use Elasticsearch; build your relevance tuning

## In Practice
Method defaults to buy/managed for commodity capabilities: Auth0 for authentication, Stripe for payments, SendGrid for email, Algolia or Elasticsearch for search, Datadog for observability. Engineering effort is reserved for product differentiators. Build decisions are documented with TCO analysis.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Build vs. Buy**: Default to buy for commodity capabilities — auth, payments, email, search, observability all have excellent managed solutions that would take months to build to the same quality. Build when the capability is your competitive differentiator or when no adequate solution exists. Always compute TCO over 3-5 years, not just upfront cost — "free" open source has real maintenance costs. Mitigate vendor lock-in by abstracting integrations behind interfaces. The most expensive builds are the ones that seemed easy at the start: authentication, billing, and search are all deceptively complex. → `engineering-knowledge-repository/build-vs-buy.md`

## Related Entries
- [Managed Services Tradeoffs](managed-services-tradeoffs.md) — managed services are the primary "buy" option for infrastructure capabilities
- [FinOps](finops.md) — build vs. buy decisions have direct cost implications captured in FinOps TCO analysis
- [Technical Debt Management](technical-debt-management.md) — poorly executed build decisions accumulate as technical debt

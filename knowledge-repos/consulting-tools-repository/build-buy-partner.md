---
id: build-buy-partner
tags: [technology-assessment, strategy, decision-framework]
surfaces-at: [validated-intent, requirements-analysis, application-design]
related: [tech-radar, magic-quadrant, value-chain-analysis, wardley-mapping, technical-due-diligence]
complexity: foundational
---

# Build vs. Buy vs. Partner

## What It Is
A decision framework for determining how to acquire a technology capability: build it in-house, buy a commercial product or SaaS solution, or partner with a third party (systems integrator, platform, API provider). Every technology program involves a series of build/buy/partner decisions — the framework structures those decisions around strategic differentiation, cost, speed, and risk rather than defaulting to "we'll build it" or "let's find a vendor." The right choice depends on whether the capability is a source of competitive differentiation, how mature the vendor market is, and what the total cost of ownership looks like across time horizons.

## When to Use
- Any technology program where the boundaries of custom development vs. vendor solutions need to be defined
- Solutions scoping: what is Method building, what is the client buying, and what are we integrating?
- When a client has a strong "build everything" or "buy everything" bias that needs to be challenged
- Pre-engagement: structuring the technology investment thesis before scope is defined
- Evaluating whether to replace, retain, or augment an existing system

## Key Concepts
- **Build**: Custom development that produces a proprietary capability. Choose when:
  - The capability is a source of competitive differentiation (customers pay for it, competitors can't easily replicate it)
  - No vendor solution meets requirements with acceptable customization
  - IP ownership and control are strategic requirements
  - Long-term cost of ownership of a vendor solution exceeds build cost
- **Buy**: Commercial off-the-shelf (COTS) product or SaaS subscription. Choose when:
  - The capability is commodity or undifferentiated (accounting, HR, email)
  - Vendor solutions are mature, well-supported, and widely adopted
  - Speed to capability and reduced operational burden outweigh customization flexibility
  - The vendor's roadmap investment would cost more to replicate internally
- **Partner**: Integrate with a third-party API, platform, or service. Choose when:
  - The capability is highly specialized and the partner is the market leader (payments via Stripe, maps via Google, identity via Okta)
  - The partnership creates a distribution or ecosystem advantage beyond the capability itself
  - The integration cost and dependency risk are acceptable
- **Wardley Mapping Alignment**: Components in the Genesis/Custom-Built zones → Build. Product/Rental zone → Buy. Commodity/Utility zone → Partner or buy managed service
- **Total Cost of Ownership**: Build decisions are frequently undercosted. Include: development cost, ongoing maintenance, upgrades, talent retention, security patching. Vendor solutions are frequently undercosted on the other side: licensing, integration, migration lock-in, renewal leverage
- **Hybrid Reality**: Most programs are a mix. The framework's value is making the reasoning explicit for each capability rather than defaulting to a blanket policy

## Method Application
Used at the start of every program to define what Method is responsible for building and what the client is sourcing. Build/Buy/Partner decisions made without this framework tend to expand build scope unnecessarily (developer bias toward building) or lock in vendor dependencies without exit planning (procurement bias toward known vendors).

## Consulting Insight
🎯 **Consulting Tool — Build vs. Buy vs. Partner**: The most common mistake is defaulting to Build for capabilities that are commodity and Buy for capabilities that are differentiating. Map each capability to its competitive importance first: if customers don't choose you because of it, buy it; if they do, build it. The Build decision is also a commitment — build means you're now in the business of maintaining that capability indefinitely. Make sure the client understands total cost of ownership, not just development cost. → `consulting-tools-repository/build-buy-partner.md`

## Related Entries
- [Tech Radar](tech-radar.md) — radar ring placement informs build/buy positioning
- [Magic Quadrant](magic-quadrant.md) — vendor landscape research informs the buy option
- [Value Chain Analysis](value-chain-analysis.md) — activities that create differentiation are Build candidates; commodity activities are Buy
- [Wardley Mapping](wardley-mapping.md) — evolution axis directly maps to build/buy/partner decision
- [Technical Due Diligence](technical-due-diligence.md) — due diligence validates build vs. buy assumptions about existing systems

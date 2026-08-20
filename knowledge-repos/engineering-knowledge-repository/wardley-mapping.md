---
id: wardley-mapping
tags: [methodology, team-practices]
surfaces-at: [application-design]
related: [build-vs-buy, team-topologies, platform-as-a-product, evolutionary-architecture, managed-services-tradeoffs]
complexity: intermediate
---

# Wardley Mapping

## What It Is
A strategic situational awareness technique that visualizes the components needed to serve a user need, mapped on a two-axis canvas: vertical axis shows value chain (user need at top, enabling components below), horizontal axis shows evolution (genesis → custom built → product/rental → commodity). Created by Simon Wardley, the map makes explicit what is unique and differentiating (custom-built, left side of evolution axis) versus what is commodity and should be bought or outsourced (right side). Wardley Maps expose hidden assumptions about technology strategy — why you're building things you should be buying, or competing in areas where competition yields no differentiation.

## When to Apply
- Technology strategy decisions: build vs. buy, in-source vs. outsource
- Identifying where engineering investment creates competitive advantage vs. where it's undifferentiated infrastructure
- Platform team scope decisions: what should the platform team own vs. consume from vendors
- Before major architectural decisions with long-term strategic implications
- When an engineering team and business stakeholders have different intuitions about where to invest

## Key Concepts
- **Value Chain (Y-axis)**: Components arranged from user need (top) through enabling layers to foundational components (bottom). A ride-sharing app: "User gets a ride" → "Route optimization" → "GPS data" → "Maps infrastructure" → "Compute". The closer to the top, the more directly it serves the user
- **Evolution (X-axis)**: The evolutionary stage of each component:
  - *Genesis*: Novel, poorly understood, experimental. Competitive differentiation possible. High failure rate. Examples: novel ML approaches, new interaction paradigms
  - *Custom-Built*: Built in-house, improving with use. Understood but not commoditized. Examples: custom business logic, proprietary algorithms
  - *Product/Rental*: Available as commercial products or SaaS. Examples: Datadog, Stripe, Salesforce
  - *Commodity/Utility*: Infrastructure-level, undifferentiated, pay-per-use. Examples: compute (EC2), object storage (S3), DNS
- **Strategic Insight**: Components on the right (commodity) should be consumed, not built. Engineering resources spent building commodity infrastructure (your own monitoring stack, your own message queue) are wasted — the competitive advantage lies in the components on the left
- **Climatic Patterns**: Wardley identified patterns that repeat across industries — "everything evolves to commodity," "commoditization enables new genesis," "inertia blocks movement." These patterns inform where to expect disruption
- **Mapping Process**:
  1. Define the user and their needs
  2. Identify the components needed to serve that need (value chain)
  3. Plot each component's evolutionary stage
  4. Draw dependencies between components
  5. Identify strategic insights: mismatches (building commodity), opportunities (commoditizing custom work to reduce cost), threats (commoditization of your competitive component)
- **Practical Use in Engineering**: Wardley Maps are most practically used for build-vs-buy decisions and platform scope decisions. "Should we build our own ML feature store or use a managed service?" maps directly to the evolutionary axis — if feature stores have commoditized, build only if you have unique requirements

## In Practice
Method uses simplified Wardley Maps in solutions handoff and architecture strategy engagements. The map informs build-vs-buy decisions by making evolutionary stage explicit — if a component is in the product/commodity zone, the default is to buy/consume. Platform team scope decisions use the map to identify which internal tooling is differentiating (worth building) vs. commoditized (worth outsourcing to vendors).

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Wardley Mapping**: A Wardley Map makes explicit the question you're often avoiding: "Is this something we should be building at all?" If your engineering team is building commodity infrastructure — a monitoring stack, a deployment pipeline, a message queue — that's undifferentiated labor that could be purchased. The value chain plus evolution axes together answer where to invest: build what is differentiating (left side, custom), consume what is commoditized (right side). You don't need perfect maps — even rough placement reveals strategic misalignments. → `engineering-knowledge-repository/wardley-mapping.md`

## Related Entries
- [Build vs. Buy](build-vs-buy.md) — Wardley Mapping is the strategic framework that informs build vs. buy decisions
- [Team Topologies](team-topologies.md) — Wardley Maps help identify which components deserve platform team investment vs. external sourcing
- [Platform as a Product](platform-as-a-product.md) — platform scope decisions benefit from mapping component evolution to identify differentiating investment
- [Evolutionary Architecture](evolutionary-architecture.md) — Wardley Maps inform architectural fitness functions and evolution strategy
- [Managed Services Tradeoffs](managed-services-tradeoffs.md) — Wardley's commodity zone maps directly to managed service candidates

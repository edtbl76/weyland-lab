---
id: wardley-mapping
tags: [systems-thinking, strategy, technology-assessment]
surfaces-at: [validated-intent, requirements-analysis, application-design]
related: [build-buy-partner, tech-radar, value-chain-analysis, bcg-matrix, architecture-tradeoff-analysis]
complexity: advanced
---

# Wardley Mapping

## What It Is
A visual strategy tool developed by Simon Wardley that maps an organization's value chain on a two-axis canvas: a vertical axis representing the value chain (from user need at the top to underlying components at the bottom) and a horizontal axis representing the evolution of each component (from Genesis through Custom-Built, Product/Rental, to Commodity/Utility). The resulting map makes visible how the components of a business or system are positioned relative to their maturity — revealing where to invest (novel components that create differentiation), where to buy or outsource (commodity components), and how the landscape is likely to shift as components evolve. Wardley Maps are particularly powerful for technology strategy because they connect component evolution to strategic investment decisions.

## When to Use
- Technology strategy engagements: determining where to invest in custom development vs. commercial solutions
- When a client is building commodity components (wasting investment on undifferentiated infrastructure)
- Before major architecture decisions: mapping the component landscape reveals what needs to be built vs. bought
- Identifying strategic opportunities: components moving from Product to Commodity create disruption opportunities
- Communicating technology investment strategy to executive stakeholders who need a visual argument

## Key Concepts
- **Value Chain Axis (Vertical)**: Maps the dependency chain from user need (top) to foundational components (bottom). The top of the map is visible to the user; the bottom is invisible infrastructure. The chain shows what depends on what
- **Evolution Axis (Horizontal)**: Four stages that every component moves through — left to right:
  - *Genesis*: Novel, uncertain, experimental. Competitive advantage lives here
  - *Custom-Built*: Understood but not standardized. Still differentiating, high cost
  - *Product/Rental*: Commoditizing, vendor market emerging, standardizing. Buy rather than build
  - *Commodity/Utility*: Fully standardized, undifferentiated, utility-like. Use managed services
- **Climatic Patterns**: Predictable forces that drive component evolution — "everything evolves toward commodity," "new platforms enable higher-order innovation," "inertia resists evolution." These patterns help predict future map states
- **Anchors and Movement**: Components that are in Genesis or Custom-Built but should be moving right (toward commodity) indicate strategic inertia. Components that competitors are treating as commodity while you're still building custom indicate investment misalignment
- **Build/Buy/Partner Alignment**: Genesis and Custom-Built → Build (differentiating). Product/Rental → Buy. Commodity/Utility → Managed service or partner. The evolution axis is the basis for build/buy decisions
- **Strategic Play**: Maps reveal gameplay — anticipate component commoditization and position before it happens; identify components where competitors are caught building what will soon be commoditized; invest in components at the Genesis stage in your industry
- **Ecosystem Mapping**: Wardley Maps can map not just a company's value chain but an entire ecosystem — competitors, suppliers, customers — to reveal competitive landscape dynamics

## Method Application
Method uses Wardley Mapping in technology strategy engagements to challenge clients who are investing heavily in custom development of commodity components. The map makes visible the misallocation: "you're spending 40% of your engineering budget on components that are in the Product/Rental zone — here is a commodity alternative." Also used to identify where custom investment is justified because the component is genuinely differentiating and in the Genesis/Custom-Built zone.

## Consulting Insight
🎯 **Consulting Tool — Wardley Mapping**: The most impactful Wardley intervention is mapping a client's current technology investment against component evolution and showing them how much spend is going into the right half of the evolution axis — components that are already commoditized or fast commoditizing. This single visual often produces more strategic realignment than a full strategy deck. The power is in the axis: evolution is not a judgment, it's a direction. Components move right whether the organization plans for it or not. → `consulting-tools-repository/wardley-mapping.md`

## Related Entries
- [Build vs. Buy vs. Partner](build-buy-partner.md) — Wardley evolution axis directly maps to build/buy/partner decision criteria
- [Tech Radar](tech-radar.md) — radar ring placement reflects technology maturity; maps to evolution axis positioning
- [Value Chain Analysis](value-chain-analysis.md) — Porter's value chain provides the vertical axis of the Wardley Map
- [BCG Matrix](bcg-matrix.md) — BCG plots business units by growth/share; Wardley maps components by evolution; both inform investment allocation
- [Architecture Tradeoff Analysis](architecture-tradeoff-analysis.md) — architectural decisions for commodity components warrant different tradeoff profiles than differentiating ones

---
id: product-taxonomy
tags: [strategy, product, architecture, organizational]
surfaces-at: [validated-intent, requirements-analysis]
related: [core-domain-chart, wardley-mapping, business-model-canvas, value-chain-analysis, organizational-design]
complexity: intermediate
---

# Product Taxonomy

## What It Is
A structured classification of an organization's products, capabilities, and domains into a coherent hierarchy that serves as a shared language for architecture, strategy, and organizational decisions. Defined as a distinct technique in Nick Tune's *Architecture Modernization*, product taxonomy creates the conceptual skeleton on which domain boundaries, team structures, and modernization priorities are hung. Unlike an org chart (which reflects current structure) or a system diagram (which reflects current technology), a product taxonomy reflects the logical products and capabilities the organization delivers — independent of how they are currently organized or implemented.

## When to Use
- When an organization's product landscape is large, complex, or poorly understood — particularly in enterprise and platform engagements
- Before domain discovery work (Event Storming, Domain Storytelling) to establish shared vocabulary
- When modernization scope needs to be bounded: "which part of the product taxonomy are we touching?"
- To surface misalignment between how the business describes its products and how engineering has built them
- During M&A or integration engagements where two organizations' product landscapes need to be reconciled
- When creating a platform or API strategy — the taxonomy defines the surface area

## Key Concepts
- **Taxonomy vs. Org Chart**: A taxonomy reflects logical products and capabilities; an org chart reflects reporting lines. They rarely align perfectly — and the misalignment is informative. Teams that own capabilities that span multiple taxonomy nodes are candidates for restructuring.
- **Levels of Taxonomy**: Typically 2–3 levels. Top level: product lines or business areas. Second level: products or capabilities. Third level: features or sub-capabilities. The taxonomy should be deep enough to be useful but shallow enough to remain comprehensible.
- **Naming matters**: The vocabulary of the taxonomy should match business language, not technical language. If the business says "Client Onboarding" and the system calls it "user-provisioning-service," the taxonomy uses "Client Onboarding." Ubiquitous Language alignment is the goal.
- **Taxonomy drives domain design**: Domain boundaries should follow taxonomy nodes, not technology layers or team boundaries. A product taxonomy makes domain identification tractable — each node is a candidate domain.
- **Gaps and overlaps**: Building the taxonomy often surfaces capabilities that are owned by no one (gaps) or owned by multiple teams (overlaps). Both are architectural risks.
- **Living artifact**: Product taxonomies should be maintained as the product evolves. A stale taxonomy creates the same misalignment problems it was designed to solve.

## Method Application
Product Taxonomy is most useful at the start of Requirements Analysis in brownfield and modernization engagements. Before exploring what needs to change, establish a shared map of what exists. The taxonomy becomes the scope boundary document: decisions about what is in scope and out of scope reference taxonomy nodes rather than vague feature descriptions.

## Consulting Insight
🎯 **Consulting Tool — Product Taxonomy**: In large enterprises, one of the most common blockers to modernization is that nobody agrees on what the products actually are. Engineering has service names, Product has feature names, Sales has product names, and Finance has cost-center names — none of which map to each other. Building a product taxonomy is not glamorous, but it creates the shared language that makes every subsequent conversation faster. It also surfaces the organizational dysfunction it was built to describe: when nobody can agree on the taxonomy, the architecture will reflect that confusion. → `consulting-tools-repository/product-taxonomy.md`

## Related Entries
- [Core Domain Chart](core-domain-chart.md) — taxonomy nodes are candidates for Core / Supporting / Generic classification
- [Wardley Mapping](wardley-mapping.md) — taxonomy components can be placed on a Wardley Map to assess their evolutionary stage
- [Business Model Canvas](business-model-canvas.md) — the Value Propositions section of the BMC is an input to product taxonomy construction
- [Value Chain Analysis](value-chain-analysis.md) — taxonomy maps to the activities in the value chain
- [Organizational Design](organizational-design.md) — taxonomy is the input to team-product alignment decisions

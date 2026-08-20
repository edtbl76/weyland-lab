---
id: continuous-discovery
tags: [methodology, team-practices]
surfaces-at: [requirements-analysis, user-stories]
related: [shape-up, behavior-driven-development, domain-driven-design]
complexity: intermediate
---

# Continuous Discovery

## What It Is
A product practice where cross-functional teams conduct regular, ongoing user research — weekly touchpoints with customers — embedded directly into the product development cadence. Popularized by Teresa Torres in *Continuous Discovery Habits*. The goal: teams continuously develop a deep understanding of customer needs, generate and test assumptions, and make better product decisions before committing to building.

## When to Apply
- Product teams building user-facing software where understanding user needs is critical
- Organizations that currently do user research in large, infrequent batches — shift to small, frequent touchpoints
- When teams are building features that don't solve real user problems (output-focused, not outcome-focused)
- When product decisions are driven by internal opinions rather than validated user understanding

## When Not to Apply
- Pure infrastructure or internal tooling with no external users
- Very early-stage exploration (pre-product) where the team is still defining the problem space
- Teams without access to real customers or users for regular interviews

## Key Concepts
- **Weekly User Interviews**: The minimum cadence — 1 interview per week per team keeps insights current and prevents big-batch research bias
- **Opportunity Solution Tree (OST)**: A visual framework for mapping desired outcomes to opportunities (user needs, pain points) to solutions — maintains traceability from research to product decision
- **Assumption Testing**: Before building, identify and test the riskiest assumptions — via prototypes, experiments, or fake door tests
- **Outcome Over Output**: Frame work as achieving user outcomes (behavior change), not shipping features
- **Product Trio**: Continuous discovery works best with a cross-functional trio — product manager, designer, and engineer participating in research together

## In Practice
Continuous Discovery is Method's recommended product practice for client engagements where the client has direct user access. The weekly interview cadence is the hardest habit to establish — teams resist it when sprints are already full. The Opportunity Solution Tree connects user research to backlog decisions, making the research actionable rather than documentary.

## Engineering Knowledge
💡 **Engineering Knowledge — Continuous Discovery**: Don't save user research for quarterly UX studies. Talk to one customer per week, every week. Continuous discovery keeps the team aligned with real user needs in the current sprint, not needs from last quarter. The Opportunity Solution Tree connects what users say to what you build. The product trio (PM + designer + engineer) doing research together closes the gap between insight and implementation. → `engineering-knowledge-repository/methodologies/continuous-discovery.md`

## Related Entries
- [Behavior-Driven Development](behavior-driven-development.md) — BDD scenarios are a natural output of continuous discovery — discovered needs become executable specifications
- [Domain-Driven Design](domain-driven-design.md) — continuous discovery clarifies the domain model by surfacing how users actually think about the problem

---
id: tech-radar
tags: [technology-assessment, tooling, strategy]
surfaces-at: [validated-intent, application-design, requirements-analysis]
related: [magic-quadrant, build-buy-partner, technical-due-diligence]
complexity: foundational
---

# Tech Radar

## What It Is
A visualization tool developed by ThoughtWorks that maps technologies across two dimensions: quadrant (Techniques, Tools, Platforms, Languages & Frameworks) and adoption ring (Adopt, Trial, Assess, Hold). The ThoughtWorks Technology Radar, published biannually, is the best-known instance — a sector-neutral view of where the technology industry is heading. Organizations build their own internal Tech Radars to codify technology standards, guide team decisions, and communicate technology direction across engineering teams.

## When to Use
- Building or reviewing a client's internal technology standards and governance
- Technology strategy engagements where the client needs a shared language for technology adoption decisions
- Onboarding engineering teams onto a new client engagement — "where does this stack sit?"
- Evaluating whether a proposed technology choice is mainstream, emerging, or declining
- Framing conversations about standardization vs. experimentation in engineering organizations

## Key Concepts
- **Quadrants**:
  - *Techniques*: Development approaches, patterns, practices (e.g., micro-frontends, trunk-based development)
  - *Tools*: Software tools used in development and operations (e.g., Terraform, Datadog)
  - *Platforms*: Things you build software on — cloud, databases, infrastructure (e.g., AWS, Kubernetes)
  - *Languages & Frameworks*: Programming languages and application frameworks (e.g., Python, React)
- **Rings**:
  - *Adopt*: Proven, low-risk, recommended for use. Method/client standard
  - *Trial*: Worth pursuing in a project with risk-taking capacity. Not yet at default status
  - *Assess*: Worth exploring to understand how it will affect you. Monitor, don't implement yet
  - *Hold*: Proceed with caution. Existing use is fine, but don't start new work with it
- **Internal Radar vs. ThoughtWorks Radar**: The ThoughtWorks Radar is a starting point; an organization's radar reflects their specific context, risk tolerance, and existing investments. Start with ThoughtWorks and overlay client-specific constraints
- **Governance Value**: A radar makes implicit technology standards explicit. "Why are we using X?" → "Because it's in our Adopt ring, here's why." Reduces decision-making overhead and prevents technology sprawl
- **Living Document**: Radars go stale quickly. Commit to a review cadence (biannual) and an owner. An outdated radar is worse than no radar — it signals to engineers that governance doesn't matter
- **Radar as Communication**: The radar's primary value is communication, not governance. It tells engineers at every level what the organization values and where it's heading

## Method Application
Method uses Tech Radar in technology strategy engagements to help clients codify engineering standards. When a client has "too many technologies" (the typical brownfield scenario), a radar exercise surfaces the implicit standards that already exist and makes technology consolidation decisions structured rather than political. Also used as a rapid assessment tool at engagement start: "show me your radar" quickly reveals technology maturity and governance health.

## Consulting Insight
🎯 **Consulting Tool — Tech Radar**: If a client can't tell you what their technology standards are without a spreadsheet, they don't have technology standards — they have technology accumulation. Building an internal Tech Radar (using the ThoughtWorks format as a starting point) takes one workshop and produces a shared language for technology decisions that scales across teams. The Hold ring is the most valuable: it surfaces the "we know we shouldn't use this but we still are" conversations that block modernization programs. → `consulting-tools-repository/tech-radar.md`

## Related Entries
- [Magic Quadrant](magic-quadrant.md) — Gartner's vendor evaluation tool; used alongside Tech Radar for vendor selection decisions
- [Build vs. Buy vs. Partner](build-buy-partner.md) — radar ring placement informs build/buy positioning: commoditized = buy, differentiating = build
- [Technical Due Diligence](technical-due-diligence.md) — radar assessment is part of technical due diligence for technology acquisitions

---
id: micro-frontends
tags: [pattern, frontend, microservices]
surfaces-at: [application-design, infrastructure-design]
related: [microservices, backend-for-frontend, modular-monolith, conways-law]
complexity: intermediate
---

# Micro-Frontends

## What It Is
An architectural style that applies microservices thinking to the frontend: the web application is decomposed into independently deployable vertical slices, each owned by a separate team that builds its feature end-to-end (frontend + backend). Multiple micro-frontends are assembled at runtime or build time into a cohesive user experience. The user sees one application; the organization ships many independent pieces.

## When to Apply
- Large organizations with multiple frontend teams that are blocked by a shared, monolithic frontend codebase
- Systems where different sections of the UI have genuinely different release cadences
- When frontend teams need the same independent deployability that backend microservices teams have
- Strangler Fig migrations — incrementally replace a legacy frontend one feature at a time

## When Not to Apply
- Small teams — the coordination overhead of composing multiple frontends exceeds the benefit
- Applications with tightly integrated, highly interactive UIs where composition seams create UX problems
- When a well-structured modular monolith frontend (a "modular SPA") achieves the needed team autonomy without the runtime composition complexity
- Early-stage products where the team/ownership structure is still evolving

## Key Concepts
- **Vertical Slice**: Each micro-frontend owns one domain feature end-to-end — UI, API, data — aligned with a team's ownership boundary
- **Composition Approaches**:
  - *Build-time composition*: Micro-frontends published as packages; shell app imports them at build time. Simple, but reintroduces deployment coupling.
  - *Runtime composition (Module Federation)*: Webpack 5 Module Federation loads micro-frontends dynamically at runtime — true independent deployability.
  - *Iframe composition*: Strong isolation but poor UX integration. Rarely used except for legacy isolation.
  - *Server-side composition*: Edge includes (ESI) or server-side fragment stitching (Zalando's Tailor).
- **Shell Application**: The container app that handles shared concerns — navigation, auth, shared state — and loads micro-frontends into their slots
- **Shared Design System**: Essential — without a shared component library, the user experience fragments across teams
- **Isolation Tradeoffs**: Strong runtime isolation (separate bundles, separate frameworks) creates overhead; shared state and cross-MFE communication requires careful design

## In Practice
Micro-frontends are a Method consideration when a client has multiple large frontend teams that are genuinely blocked by a shared codebase. Webpack 5 Module Federation is the current standard for runtime composition in React/Vue/Angular ecosystems. The shared design system and UX consistency are the hardest parts — Conway's Law applies to the frontend too.

## Engineering Knowledge
💡 **Engineering Knowledge — Micro-Frontends**: Apply Conway's Law to the frontend: independent teams ship independent frontend slices. Webpack 5 Module Federation is the current standard for runtime composition — each team deploys its own bundle; the shell loads them dynamically. The hard parts: shared design system, cross-MFE state, and UX consistency across team boundaries. Start with a modular monolith frontend before going micro — the operational overhead is real. → `engineering-knowledge-repository/architectural-styles/micro-frontends.md`

## Related Entries
- [Microservices](microservices.md) — micro-frontends extend microservices thinking to the frontend
- [Backend for Frontend](backend-for-frontend.md) — each micro-frontend team often owns its own BFF
- [Conway's Law](../architectural-philosophy/conways-law.md) — micro-frontend team boundaries should drive the decomposition
- [Modular Monolith](modular-monolith.md) — start with a modular frontend before splitting into micro-frontends

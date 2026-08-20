---
id: harnessability
tags: [pattern, ai-ml, agent, architecture, code-quality, brownfield]
surfaces-at: [application-design, functional-design, code-generation]
related: [harness-engineering, harness-guides-and-sensors, clean-architecture, hexagonal-architecture, solid-principles, domain-driven-design, evolutionary-architecture]
complexity: intermediate
---

# Harnessability

## What It Is
Harnessability is the property of a codebase that makes it legible, navigable, and tractable to AI coding agents. Not all codebases respond equally well to agent-driven development. A codebase written in a strongly typed language with clear module boundaries, consistent naming conventions, and high test coverage affords structural signals that agents can read and act on reliably. A codebase with implicit conventions, large functions, weak typing, and entangled modules forces the agent to reason about more context with less signal — producing more errors and requiring more human correction.

The concept was named by Ned Letcher, who used the term "ambient affordances" to describe structural properties that make systems tractable to agents. Böckeler extended this into practical design guidance for teams choosing how to build or evolve their codebases. Greenfield projects can design for harnessability from inception; brownfield projects can improve it incrementally, though the work is harder and the need is typically greater.

## When to Apply
- Greenfield projects where AI-assisted development is planned — design for harnessability from the start, not as a retrofit
- Brownfield modernization decisions — prioritize harnessability improvements in areas where agent-driven development is planned
- Code review and technical debt triage — frame technical debt not only in terms of human readability but agent tractability
- Architecture decisions about module boundaries, type systems, and naming conventions — these directly affect how well agents can navigate the codebase

## When Not to Apply
- Short-lived throwaway scripts where long-term agent legibility is irrelevant
- Highly experimental or research code where structure rigidity would hinder exploration

## Key Concepts
- **Ambient Affordances**: Structural properties of a codebase that an agent can exploit without explicit instruction. Strong types are an ambient affordance — the agent infers constraints from the type system without needing them spelled out. Clear module boundaries are an affordance — the agent can reason about scope. Consistent naming is an affordance — the agent recognizes patterns. These reduce guide surface and sensor load by making the codebase self-documenting to the agent
- **Type Density**: Strongly typed codebases give agents more information per token of context read — type annotations communicate intent, constraints, and relationships that would otherwise require doc comments or inference. TypeScript over JavaScript, typed Python over untyped, explicit return types over inferred: each is a harnessability improvement. Type checking also becomes a free computational sensor when type density is high
- **Module Boundary Clarity**: Agents navigate codebases through imports, exports, and function signatures. Clear, stable module boundaries let an agent determine scope confidently — what can change here without affecting there. God objects, circular dependencies, and implicit coupling force agents to load more context and reason less reliably about impact
- **Test Coverage as Map**: Tests are an agent's behavioral oracle. High coverage means the agent can execute tests after any change and immediately determine whether behavior is preserved. Low coverage means behavioral correctness requires human review that cannot be automated into a sensor
- **Naming Consistency**: Consistent naming conventions (file naming, function naming, variable naming, test naming) reduce the agent's disambiguation cost. When `UserService`, `user-service.ts`, `getUserById`, and `describe('UserService')` follow a predictable pattern, the agent finds things correctly on first lookup. Inconsistency forces search-and-guess loops that consume context and produce errors
- **Harnessability Debt**: Just as technical debt accumulates costs in human development, harnessability debt accumulates agent error rates, context consumption, and human correction overhead. Teams adopting AI-assisted development inherit harnessability debt from prior architectural decisions, and paying it down has different prioritization logic than traditional tech debt (it affects automation leverage, not just human productivity)
- **Designing for Harnessability vs. Retrofitting**: Greenfield systems can bake in harnessability: strict typing from day one, enforced module boundaries via linting, test coverage gates in CI, consistent naming enforced by code review. Brownfield systems improve harnessability incrementally — starting with the areas where agents are actually working, and accepting that legacy areas with high harnessability debt need more human supervision until improved

## In Practice
Method engineering teams assess harnessability as part of brownfield engagement scoping. Indicators reviewed: type coverage, average function length, module boundary clarity (measured by coupling metrics), test coverage, and naming consistency (assessed by codebase scanning). Areas with high harnessability debt get flagged for incremental improvement before agent-driven development is planned against them. For greenfield work, harnessability requirements are added to NFR design: strict typing, test coverage floors, module boundary enforcement via linting rules.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Harnessability**: A harness is only as good as the codebase it works with. Strong typing, clear module boundaries, consistent naming, and high test coverage are not just human-readability concerns — they are the structural signals that let an agent navigate, reason about, and modify a codebase reliably. If your codebase is hard for a new human engineer to understand, it will be harder still for an agent. Designing for harnessability from day one is far cheaper than retrofitting it when agent error rates reveal the debt. → `engineering-knowledge-repository/harnessability.md`

## Related Entries
- [Harness Engineering](harness-engineering.md) — harnessability describes properties of the target codebase; the harness wraps the agent operating on it
- [Harness Guides and Sensors](harness-guides-and-sensors.md) — high harnessability reduces guide surface and makes sensors cheaper and more reliable
- [Clean Architecture](clean-architecture.md) — clean architecture principles improve harnessability through dependency rules and clear layer boundaries
- [Hexagonal Architecture](hexagonal-architecture.md) — hexagonal architecture creates naturally harness-friendly structures: isolated domain logic, testable without framework dependencies
- [SOLID Principles](solid-principles.md) — single responsibility and interface segregation directly improve harnessability by keeping units small and boundaries clear
- [Domain-Driven Design](domain-driven-design.md) — bounded contexts create the explicit module boundaries that make codebases agent-tractable
- [Evolutionary Architecture](evolutionary-architecture.md) — fitness functions for harnessability (type coverage, coupling metrics, test coverage) can be automated as architectural gates

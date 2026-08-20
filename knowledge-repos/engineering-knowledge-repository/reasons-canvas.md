---
id: reasons-canvas
tags: [pattern, ai-ml, methodology, prompt-engineering, code-generation, specification, governance]
surfaces-at: [application-design, functional-design, code-generation]
related: [structured-prompt-driven-development, aidlc, prompt-engineering, architecture-decision-records, harnessability, test-driven-development, behavior-driven-development]
complexity: foundational
---

# REASONS Canvas

## What It Is
The REASONS Canvas is a seven-part structured prompt template used in Structured-Prompt-Driven Development (SPDD) to produce complete, governed specifications before any code is generated. Each section of the canvas addresses a different concern — from domain modeling and intent through execution strategy to cross-cutting standards and hard constraints. Together, the seven sections produce a single document that functions as the authoritative specification, the prompt for code generation, and the record of design decisions for that unit of work.

REASONS is an acronym:

| Letter | Section | Layer | Purpose |
|---|---|---|---|
| **R** | Requirements | Abstract | Problem definition and definition of done |
| **E** | Entities | Abstract | Domain entities and their relationships |
| **A** | Approach | Abstract | Solution strategy — how the requirements will be met |
| **S** | Structure | Abstract | System placement — components, dependencies, module boundaries |
| **O** | Operations | Specific | Concrete, ordered, testable implementation steps |
| **N** | Norms | Governance | Cross-cutting engineering standards (naming, observability, defensive coding) |
| **S** | Safeguards | Governance | Non-negotiable boundaries — invariants, performance limits, security rules |

The canvas separates the *abstract* layer (design intent, domain model, strategic approach) from the *specific* layer (concrete steps) and the *governance* layer (standards and hard constraints). This separation is what gives SPDD its alignment gate: a team reviews the abstract and governance layers before the specific operations are handed to the model for code generation. Design disagreements surface at the Canvas review, not during code review of generated output.

## When to Apply
- Before generating code for any unit with meaningful business logic, compliance requirements, or cross-service dependencies
- When multiple engineers need shared understanding of a feature's design before any code is written
- In regulated or compliance-heavy domains where traceability from business intent to implementation is required
- When reusing existing domain models, Norms, or Safeguards across multiple features — the canvas is the reuse surface
- As the Functional Design artifact in the AIDLC Construction phase (replaces or extends the `/spec` output)

## When Not to Apply
- Trivial CRUD with no business rules — the overhead exceeds the value
- Exploratory spikes where the design is the output, not the input
- Throwaway scripts or one-off utilities with no governance requirements

## Key Concepts

### R — Requirements
The problem statement and definition of done. Not user stories or acceptance criteria (those belong in the AIDLC User Stories stage) — this is a direct, declarative statement of what the unit must accomplish and how correctness will be verified. Includes: business context, functional scope, explicit out-of-scope items, and the done condition the Evaluator or test suite will check.

### E — Entities
The domain model for this unit. Entity names, attributes, relationships, and invariants. The Entities section is where naming is locked — entity names defined here flow through to code, API contracts, and database schemas. Changing entity names after this section is approved is a refactor, not a correction. This is also where the canvas connects to DDD bounded context design: entities defined here are the ubiquitous language for the unit.

### A — Approach
The solution strategy — not implementation steps (those are in Operations), but the pattern, algorithm, or architectural approach that will satisfy the Requirements. Examples: "Use the Repository pattern to abstract storage. Apply optimistic locking for concurrent updates. Model state transitions as an explicit state machine." The Approach section is where architectural decisions are recorded; it feeds Architecture Decision Records for decisions with cross-cutting impact.

### S — Structure
System placement and dependencies. Which module or service owns this unit? What does it depend on? What does it expose? This section defines the module boundary, the interface contract, and the dependency graph for the unit being built. It is the primary mechanism for preventing architectural drift — the model cannot make structural decisions during generation that contradict what is defined here. In Method AIDLC, this section maps to the Application Design artifact for the unit.

### O — Operations
The abstract strategy broken into concrete, ordered, testable implementation steps. This is the only section that instructs the model on what to do step-by-step. Each operation has a clear acceptance criterion. Operations are ordered by dependency — the model executes them in sequence, verifying each before proceeding. This section drives Code Generation Part 1 (the plan) in AIDLC. Operations are not pseudocode — they are implementation-language-agnostic instructions that the model translates.

### N — Norms
Cross-cutting engineering standards that apply to this unit. Norms are typically reused across Canvases rather than written fresh each time — a service's Norms section is stable across all features in that service. Examples: error handling conventions, logging format and levels, naming conventions, test coverage expectations, observability requirements (what must be instrumented), API response shape standards. Norms are enforced by the Evaluator or Code Reviewer; violations are non-compliance findings.

### S — Safeguards
Non-negotiable boundaries. These are hard constraints that the generated code must never violate regardless of any other consideration. Examples: "No PII in logs," "All writes must be idempotent," "Response time under 200ms at p99 under specified load," "No direct database access from the API layer." Safeguards are the governance layer — they encode regulatory requirements, security mandates, architectural invariants, and performance SLAs. In Method AIDLC, Safeguards are extracted to `memory/constraints.md` (Rock 13) so they survive across sessions and iterations without requiring re-derivation from the Canvas.

## In Practice
In Method AIDLC, the REASONS Canvas is the primary artifact produced during Functional Design for any unit with meaningful business logic. The Specification Writer persona produces it using the `/spec` skill. The canvas file lives at `aidlc-docs/construction/{unit-name}/reasons-canvas.md`. It is reviewed and approved at the Functional Design gate before Code Generation begins. The Operations section is the direct input to Code Generation Part 1 (the `/plan` output references canvas operations by number). The Safeguards section is extracted to `memory/constraints.md` at approval time. After code is written, `/spdd-sync` updates the canvas if refactoring changed the Structure or Approach; this keeps the canvas current as the unit evolves across iterations.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — REASONS Canvas**: The canvas's value is in the separation of concerns across its three layers. The abstract layer (R, E, A, S) forces design decisions to happen before generation — which is where they are cheapest to make and change. The governance layer (N, S) encodes standards and constraints that are otherwise only enforced by human reviewer memory. The specific layer (O) is the only part the model needs for generation; the other six sections exist to make that generation deterministic. Teams that skip the Entities section produce code with inconsistent naming. Teams that skip the Safeguards section produce code that violates invariants under edge conditions. The canvas is complete only when all seven sections are present and reviewed. → `engineering-knowledge-repository/reasons-canvas.md`

## Related Entries
- [Structured-Prompt-Driven Development](structured-prompt-driven-development.md) — the REASONS Canvas is SPDD's primary artifact; see SPDD for the full closed-loop workflow and sync commands
- [AIDLC](aidlc.md) — the Canvas is the Functional Design artifact within the AIDLC Construction phase; its sections map to AIDLC stage outputs
- [Prompt Engineering](prompt-engineering.md) — the canvas is a formal system prompt template; the Norms and Safeguards sections are explicit constraint and format specifications
- [Architecture Decision Records](architecture-decision-records.md) — Approach and Structure section decisions that have cross-cutting impact should produce ADRs; the Canvas is the source document
- [Harnessability](harnessability.md) — the Safeguards and Norms sections directly encode harnessability requirements: the structural constraints an agent must respect
- [Test-Driven Development](methodologies/test-driven-development.md) — the Operations section defines testable steps with acceptance criteria; this is TDD's "define the test first" principle applied at the specification level
- [Behavior-Driven Development](methodologies/behavior-driven-development.md) — the Requirements section's definition of done maps to BDD scenarios; SPDD and BDD share the "lock intent before implementation" discipline

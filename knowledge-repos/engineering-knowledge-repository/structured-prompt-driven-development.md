---
id: structured-prompt-driven-development
tags: [pattern, ai-ml, methodology, prompt-engineering, code-generation, governance]
surfaces-at: [application-design, functional-design, code-generation]
related: [reasons-canvas, aidlc, prompt-engineering, autonomous-coding-loop, planner-generator-evaluator, harnessability, architecture-decision-records, human-in-the-loop]
complexity: intermediate
---

# Structured-Prompt-Driven Development (SPDD)

## What It Is
SPDD is an engineering methodology that treats prompts as first-class delivery artifacts — version-controlled, reviewed, and kept in sync with the code they generate. Rather than using AI through ad hoc conversations that produce disposable outputs, SPDD formalizes prompts into governed specifications that live alongside code in the repository. The prompt is the authoritative design document; the code is its implementation. When they diverge, the prompt is corrected first.

The core rule: **"When reality diverges, fix the prompt first — then update the code."**

The methodology was developed by Wei Zhang and Jessie Jie Xia at Thoughtworks and published on martinfowler.com. It emerged from production delivery experience where AI-generated code moved fast locally but created coordination, review, and traceability problems at team scale. SPDD addresses the organizational layer that pure prompt engineering ignores — the methodology is as much about team workflow and governance as it is about prompt quality.

The primary artifact is the **REASONS Canvas** — a seven-part structured prompt template. See the [REASONS Canvas](reasons-canvas.md) entry for the full template definition.

## When to Apply
- Feature development where business rules, constraints, and compliance requirements must be traceable to implementation
- Scaled or standardized delivery across multiple services or teams where consistency and reuse matter
- Regulated environments (financial systems, healthcare, compliance-heavy domains) where audit trails linking intent to code are required
- Multi-person delivery where more than one engineer needs to understand and review the prompt design, not just the output code
- Brownfield enhancement where accumulated prompt assets representing prior decisions should be reused as context for new work

## When Not to Apply
- Exploratory spikes or prototypes where speed matters more than governance
- One-off scripts or throwaway utilities with no reuse value
- Pure creative or visual work where output quality is driven by taste, not logical correctness
- Firefighting hotfixes where the priority is stopping the incident, not prompt governance (SPDD can govern post-incident)
- Poorly defined domains with no clear business rules — SPDD requires alignment to lock; it cannot substitute for alignment that doesn't exist

## Key Concepts
- **Prompt-as-Artifact**: Prompts are not chat inputs; they are maintained delivery artifacts. They live in version control, receive code review, follow a consistent structure (the REASONS Canvas), and are updated as requirements change. A prompt that goes stale is a defect — it means the specification and the implementation have silently diverged
- **Closed-Loop Workflow**: SPDD enforces two-way synchronization between prompt and code at two scales. Within an iteration: logic corrections update the prompt before regenerating code; refactoring updates the code then syncs back to the prompt. Across iterations: accumulated prompt assets (domain models, norms, safeguards, decisions) become the baseline context for the next enhancement. The loop closes in both directions
- **Two-Way Sync**: `/spdd-sync` updates the Canvas when code changes (refactoring → prompt). `/spdd-prompt-update` updates code when requirements change (requirements → prompt → code). Without explicit sync commands, prompts silently decay — they describe the system as it was when the prompt was written, not as it is now
- **Abstraction-First**: Before any code is generated, SPDD requires that entity relationships, module structure, and component dependencies are designed explicitly in the Canvas (Entities + Structure sections). Code generation is constrained to this design; the model does not make architectural decisions during generation. This is the primary mechanism for reducing hallucination and architectural drift
- **Alignment Gate**: The Canvas is reviewed and approved before code generation begins — ensuring business intent, design decisions, and constraints are locked before any implementation is produced. This shifts review effort from "spot the bug in the output" to "check the intent in the spec," which is faster and catches more structural errors
- **Prompt Library**: Over time, individual Canvas files accumulate into a reusable organizational library. Norms and Safeguards sections in particular reuse across features — a financial service's regulatory safeguards are written once and referenced by all subsequent Canvases in that domain. The library is a compounding asset
- **openspdd CLI**: The reference tooling that implements the SPDD workflow as repeatable slash commands — `/spdd-analysis`, `/spdd-reasons-canvas`, `/spdd-generate`, `/spdd-prompt-update`, `/spdd-sync`, and optional commands for API testing and story generation

## In Practice
SPDD maps cleanly onto the Method AIDLC Construction phase. The REASONS Canvas is produced during Functional Design (Specification Writer, using the `/spec` skill). The Canvas's Operations section drives Code Generation Part 1 planning (`/plan`). The Safeguards section feeds `constraints.md` in the Memory Architecture (Rock 13). The Canvas itself is a versioned artifact in `aidlc-docs/` — it is the prompt-as-artifact for the unit being built. The `/spdd-sync` discipline maps directly to the commit protocol: when code changes during refinement, the Canvas is updated before the commit is closed.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — SPDD**: The methodology's central insight is that unstructured AI-assisted development is fast locally and expensive at scale — the governance overhead of ad hoc prompting compounds across a team. Treating the prompt as the specification (not documentation written after the fact) forces the alignment conversation to happen before implementation, where it is cheap. The two-way sync discipline is what makes the approach sustainable: `/spdd-sync` keeps the Canvas from going stale when code changes; `/spdd-prompt-update` keeps code from drifting when requirements change. The REASONS Canvas gives teams a shared vocabulary for what a "complete" spec looks like — Norms and Safeguards in particular are the sections most often skipped in informal prompting and most often responsible for quality failures. → `engineering-knowledge-repository/structured-prompt-driven-development.md`

## Related Entries
- [REASONS Canvas](reasons-canvas.md) — the seven-part structured prompt template that is SPDD's primary artifact
- [AIDLC](aidlc.md) — AIDLC rule files are governed prompt artifacts at the methodology layer; SPDD formalizes the same discipline at the feature/unit layer
- [Prompt Engineering](prompt-engineering.md) — SPDD extends prompt engineering from craft into methodology; the REASONS Canvas is a formal system prompt template
- [Autonomous Coding Loop](autonomous-coding-loop.md) — SPDD's Canvas drives autonomous generation runs; plan files and the closed-loop workflow share the same "durable state on disk" principle
- [Planner-Generator-Evaluator](planner-generator-evaluator.md) — SPDD's alignment gate (Canvas review before generation) is a lightweight planner/evaluator separation; full PGE extends this with a dedicated evaluator agent
- [Harnessability](harnessability.md) — SPDD's Safeguards and Norms sections explicitly encode harnessability requirements — the constraints an AI agent must respect when navigating the codebase
- [Architecture Decision Records](architecture-decision-records.md) — the Canvas Approach and Structure sections capture architectural decisions; a mature SPDD workflow produces ADRs from Canvas review outcomes
- [Human in the Loop](human-in-the-loop.md) — the alignment gate is a HITL checkpoint before generation; the Canvas review is the human's primary leverage point in SPDD

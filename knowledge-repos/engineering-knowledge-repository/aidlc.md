---
id: aidlc
tags: [pattern, ai-ml, methodology, orchestration, delivery, workflow]
surfaces-at: [application-design, requirements-analysis, code-generation]
related: [harness-engineering, agent-patterns, multi-agent-systems, human-in-the-loop, prompt-engineering, context-window-management, haas, autonomous-coding-loop, structured-prompt-driven-development]
complexity: intermediate
---

# AI-assisted Development Lifecycle (AIDLC)

## What It Is
AIDLC is an architectural pattern for encoding a delivery methodology as structured rule files that an AI model reads and orchestrates at runtime. Instead of relying on human discipline to consistently apply a delivery process, the methodology is externalized into a machine-readable rule set — stage definitions, gating conditions, question formats, knowledge surfacing rules, audit requirements — and an AI model becomes the workflow engine that executes it.

The pattern separates three concerns: the **orchestration instructions** (CLAUDE.md or equivalent entry point), the **rule files** (stage-level behavior definitions), and the **knowledge repositories** (domain and engineering context surfaced at the right moment). The AI reads the entry point, resolves rule files through a defined lookup hierarchy, and executes the workflow adaptively based on context.

AIDLC is a specific application of harness engineering at the methodology layer: the harness is the delivery process itself.

## When to Apply
- Organizations that want to scale consistent delivery practices without relying on individual consultant discipline
- Consulting or delivery firms where methodology adherence is a quality and client commitment issue
- Teams building AI-powered workflow systems where the workflow has defined stages, gates, and conditional logic
- Any system where an AI model must follow a structured process rather than free-form reasoning — compliance workflows, onboarding processes, procurement processes, audit workflows

## When Not to Apply
- Exploratory or R&D work where workflow rigidity would kill the discovery process
- Simple task automation where a single prompt or a few chained calls is sufficient
- Teams without the discipline to maintain the rule files — an AIDLC with stale or incorrect rules produces confidently wrong behavior

## Key Concepts
- **Orchestration Entry Point**: A single file (e.g., CLAUDE.md) that the AI reads first. It defines the overall workflow, phase structure, mandatory behaviors, and how to resolve rule files. This is the harness's system prompt analog — it sets the frame for everything else
- **Rule Files**: Stage-level behavior definitions — what to do, in what order, with what gates. Rule files are the methodology encoded as prose and structure that an AI can interpret and execute. They are versioned artifacts, not documentation
- **Two-Layer Rule Resolution**: Rule files are resolved through a priority hierarchy — an overlay layer is checked first; a base layer is the fallback. This enables teams to override specific stages without forking the entire methodology. New stages live only in the overlay; unchanged stages load from base unchanged
- **Adaptive Depth**: AIDLC stages are not one-size-fits-all. The workflow assesses complexity and context — a simple request executes a minimal path; a complex, high-risk request executes full depth. The AI determines appropriate depth from the rule file's criteria, not by asking the user every time
- **Stage Gating**: Each stage has a declared owner (who does the work) and a gate approver (who must confirm before the workflow proceeds). Gates are enforced by the harness — the AI will not proceed past a gate until it receives explicit confirmation. This encodes accountability into the workflow itself
- **Knowledge Surfacing**: At defined stages, the workflow consults indexed knowledge repositories (engineering patterns, consulting tools, industry vertical context) and surfaces relevant entries inline — before questions are asked or recommendations are made. The AI doesn't need to know everything; it needs to know where to look
- **Audit Trail**: Every user input and AI response is logged with a timestamp to an append-only audit file. The audit trail is a first-class workflow artifact — it enables review, debugging, and accountability. Harness implementations must protect the audit file from overwrite operations
- **Iteration Awareness**: AIDLC workflows distinguish between Iteration 0 (full-depth execution, greenfield behavior) and Iteration N (delta-only execution, building on prior artifacts). This prevents re-doing completed work and keeps subsequent iterations efficient

## In Practice
Method's AIDLC implementation uses CLAUDE.md as the orchestration entry point. Rule files live in `.method-rule-details/` (Method overlay) and `.aidlc-rule-details/` (base AIDLC). Three knowledge repositories — Engineering Knowledge, Consulting Tools, and Industry Verticals — are indexed for AI lookup and surfaced at the stages where they are relevant. Each stage names its owner and gate approver from a team ownership model defined in common rules. Audit logging is append-only and enforced by the orchestration instructions.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — AIDLC**: Encoding a methodology as rule files that an AI executes is fundamentally different from writing documentation that humans read. Rule files must be precise, unambiguous, and structured for machine interpretation — not just human comprehension. The two-layer resolution pattern is what makes the approach maintainable: teams override only what they need to; the base methodology handles the rest. Stage gates are only meaningful if the harness enforces them — if the AI can be talked past a gate, the gate doesn't exist. Treat the rule files and knowledge repositories as production artifacts: version them, review changes, and audit their effect on workflow behavior. → `engineering-knowledge-repository/aidlc.md`

## Related Entries
- [Harness Engineering](harness-engineering.md) — AIDLC is an application of harness engineering; the methodology is the harness
- [Agent Patterns](agent-patterns.md) — AIDLC orchestrators are agents; stages with tool use are agent sub-tasks
- [Multi-Agent Systems](multi-agent-systems.md) — advanced AIDLC implementations decompose stage execution across specialized sub-agents
- [Human in the Loop](human-in-the-loop.md) — stage gates are HITL checkpoints; AIDLC enforces them structurally, not by convention
- [Prompt Engineering](prompt-engineering.md) — rule files are structured prompts; the same principles of clarity, constraint, and format specification apply
- [Context Window Management](context-window-management.md) — long-running AIDLC workflows accumulate significant context; rule files should specify what to load when, not load everything always
- [Harness-as-a-Service](haas.md) — HaaS platforms provide the managed runtime that AIDLC orchestration runs on top of
- [Autonomous Coding Loop](autonomous-coding-loop.md) — long-horizon construction phase execution is an autonomous coding loop operating within the AIDLC framework
- [Structured-Prompt-Driven Development](structured-prompt-driven-development.md) — SPDD formalizes the prompt-as-artifact discipline at the feature level; AIDLC rule files are governed prompt artifacts at the methodology level — the same principle applied at different scales

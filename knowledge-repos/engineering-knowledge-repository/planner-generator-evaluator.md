---
id: planner-generator-evaluator
tags: [pattern, ai-ml, agent, multi-agent, quality, orchestration]
surfaces-at: [application-design, nfr-requirements]
related: [multi-agent-systems, harness-engineering, autonomous-coding-loop, harness-guides-and-sensors, human-in-the-loop, agent-patterns, llm-evaluation, structured-prompt-driven-development]
complexity: advanced
---

# Planner-Generator-Evaluator

## What It Is
A three-role agent decomposition pattern for AI tasks where quality and correctness are first-order requirements. The task is split across three specialized agents: a **Planner** that decomposes the goal into a structured plan with explicit acceptance criteria, a **Generator** that implements individual plan steps, and an **Evaluator** that assesses the generator's output against the acceptance criteria independently. The generator and evaluator never share context — the evaluator's independence is the source of its value.

The pattern is motivated by a consistent finding in production AI systems: agents that generate output and then evaluate their own output are systematically over-optimistic. They find what they expect to find. Separating generation from evaluation into distinct agents with separate contexts eliminates this self-assessment bias. Anthropic's long-running agent research explicitly endorses this separation, noting that it outperforms self-evaluation for tasks with a meaningful quality bar.

The pattern is sometimes described as "GANs for prose and code" — the generator and evaluator operate in tension, and that tension improves output quality.

## When to Apply
- Code generation tasks where correctness cannot be fully verified by automated tests alone — security-sensitive code, complex business logic, architectural conformance
- Long autonomous runs (see Autonomous Coding Loop) where accumulated quality drift compounds into broken output at the end
- Any task where self-evaluation by the generating agent has produced systematically optimistic assessments ("looks good to me" on broken code)
- High-stakes generation tasks where a human review gate is desirable but expensive — the evaluator agent is a scalable pre-filter

## When Not to Apply
- Tasks with strong computational verification — if a test suite and typecheck fully specify correctness, a separate evaluator adds cost without benefit
- Simple single-step generation where the overhead of a three-agent system is unjustified
- Exploratory or creative tasks where there is no well-defined acceptance criterion for the evaluator to apply

## Key Concepts
- **Planner Role**: Receives the task goal and produces a structured plan — decomposed steps, dependencies, and explicit acceptance criteria for each step. The acceptance criteria are the contract between planner and evaluator; they specify what "done" means before any generation occurs. The planner should not generate implementation; its output is a plan file, not code. Separating planning from generation keeps the generator focused and prevents mid-task re-planning
- **Generator Role**: Receives individual plan steps (one at a time) and produces the output — code, text, configuration, test cases, or other artifacts. The generator works against the acceptance criteria defined by the planner but does not evaluate its own output. Its context contains the task, the plan step, and necessary codebase context. It does not contain evaluator feedback (to prevent it from optimizing for looking good to the evaluator rather than actually being correct)
- **Evaluator Role**: Receives the generator's output and the acceptance criteria for the plan step being evaluated. It does not have access to the generator's reasoning or chain of thought — only the output and the criteria. The evaluator produces a pass/fail verdict with specific findings. Failed evaluations are returned to the generator with the specific deficiencies, not a vague "try again." The evaluator's independence is structural, not by convention — it is a separate agent call with a separate system prompt and context
- **Sprint Contracts**: The negotiation between planner and evaluator on acceptance criteria before the generator begins work. Ambiguous criteria produce inconsistent evaluation; the sprint contract surfaces and resolves that ambiguity upfront. Concretely: the planner produces draft criteria; the evaluator reviews them for completeness and testability; the final criteria are committed to the plan file before generation starts
- **Evaluation Feedback Loop**: When the evaluator fails a generator's output, the failure is structured: specific criterion not met, evidence from the output, suggested remediation direction. The generator receives this structured feedback and produces a revised output. The loop continues until the evaluator passes or a max-iteration limit is reached. At the limit, the task is escalated to human review
- **Context Firewall**: The evaluator's context must not contain the generator's reasoning or self-commentary. If the generator explains why it made a decision, the evaluator reads that explanation and anchors to it. The context firewall enforces that the evaluator judges the output on its merits against the criteria, not against the generator's intentions

## In Practice
Method implements this pattern for security-sensitive code generation and for large autonomous refactors where human review time is constrained. The planner, generator, and evaluator are distinct system prompts instantiated as separate agent calls. Plan files are written to disk; acceptance criteria are co-located with each plan step as a structured checklist. Evaluator feedback is structured as JSON with a pass/fail field, a list of specific deficiency findings, and a severity rating per finding. Generator retries are capped at three; after three failures the step is flagged for human review with the full evaluation history.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Planner-Generator-Evaluator**: Agents that grade their own work grade it generously. The fix is structural, not prompt-based — you cannot tell a single agent to "be more critical of your own output" and get independent evaluation. Separate the roles. The evaluator's independence is only real if it cannot read the generator's reasoning, only its output. Sprint contracts — agreeing what "done" means before generation starts — catch scope ambiguity that would otherwise surface as a loop that never terminates. When the evaluator keeps failing the same criterion, that's signal to improve the guide, not just to retry the generator. → `engineering-knowledge-repository/planner-generator-evaluator.md`

## Related Entries
- [Multi-Agent Systems](multi-agent-systems.md) — planner-generator-evaluator is a three-agent pattern; the coordination patterns and failure modes of multi-agent systems apply
- [Harness Engineering](harness-engineering.md) — the context firewall, role separation, and feedback loop are harness design decisions
- [Autonomous Coding Loop](autonomous-coding-loop.md) — planner/executor decomposition in autonomous loops is a two-role variant; adding the evaluator role completes the pattern
- [Harness Guides and Sensors](harness-guides-and-sensors.md) — the evaluator is an inferential sensor; the sprint contract is a guide
- [Human in the Loop](human-in-the-loop.md) — the escalation path when the evaluator loop exceeds max retries; HITL is the backstop for evaluation failures
- [Agent Patterns](agent-patterns.md) — the three roles each implement an agent pattern (planner: decomposition; generator: ReAct; evaluator: judge)
- [LLM Evaluation](llm-evaluation.md) — the evaluator role is an application of LLM-as-judge evaluation patterns to agent output
- [Structured-Prompt-Driven Development](structured-prompt-driven-development.md) — SPDD's alignment gate (Canvas review before generation) is a lightweight Planner/Evaluator separation; the REASONS Canvas is the planner output that constrains the generator

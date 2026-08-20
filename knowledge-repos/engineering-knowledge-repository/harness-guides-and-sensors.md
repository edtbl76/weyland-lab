---
id: harness-guides-and-sensors
tags: [pattern, ai-ml, agent, orchestration, testing, quality]
surfaces-at: [application-design, nfr-requirements, nfr-design]
related: [harness-engineering, agent-patterns, evolutionary-architecture, ci-cd, mutation-testing, llm-guardrails, llm-observability]
complexity: intermediate
---

# Harness Guides and Sensors

## What It Is
A taxonomy for classifying the controls in an AI agent harness by when they act and how they evaluate. **Guides** are feedforward controls — they anticipate agent behavior and steer it before the agent acts, increasing the probability of quality output on the first attempt. **Sensors** are feedback controls — they observe what the agent produced and enable self-correction before human review. Well-designed harnesses combine both; relying exclusively on either creates systematic gaps.

The taxonomy comes from Birgitta Böckeler's work on coding agent harnesses and provides a principled way to audit harness coverage: for any failure mode you're trying to prevent, you should be able to name which guide reduces its probability and which sensor catches it when it occurs anyway.

## When to Apply
- Designing the quality and safety layer of a new agent harness — use the guide/sensor frame to ensure both feedforward and feedback coverage
- Auditing an existing harness for gaps — any failure mode with a sensor but no guide will recur at a predictable rate; any failure mode with a guide but no sensor has no verification
- Planning CI integration for agent workloads — guides and sensors map cleanly to pre-task and post-task pipeline stages
- When building architecture fitness functions for AI-generated code — this is a direct application of guides and sensors to maintainability and architectural conformance

## When Not to Apply
- Simple single-turn completions with no workflow execution — the overhead of a structured control taxonomy isn't justified
- Prototyping — add guides and sensors once failure patterns are visible, not speculatively

## Key Concepts
- **Guides (Feedforward Controls)**: Information, constraints, and context provided before the agent acts. Examples: system prompts defining coding conventions, `AGENTS.md` files injected at session start, skill files that scope the agent's task, CLAUDE.md rules about what to avoid. Guides shift the agent's prior toward correct behavior but cannot guarantee it
- **Sensors (Feedback Controls)**: Checks that run after the agent acts and surface failures back into the loop. Examples: typecheck on every file edit, lint after code generation, test suite execution after changes, an LLM reviewer subagent that flags anti-patterns. Sensors enable self-correction without human intervention
- **Computational Controls**: Deterministic, fast, CPU-based — linters, type checkers, test runners, static analysis. These operate in milliseconds to seconds and produce reliable binary results. Right for the inner loop (pre-commit, post-edit)
- **Inferential Controls**: Semantic analysis powered by an LLM — code review agents, "LLM as judge" evaluators, architectural conformance reviewers. Slower, more expensive, and less deterministic than computational controls, but capable of richer semantic judgment that no static tool can replicate. Right for the outer loop (post-integration, periodic)
- **Timing Layers**: Controls should be distributed based on cost and speed, following shift-left principles. Fast computational sensors belong pre-commit. Expensive inferential sensors belong in CI pipelines. Periodic analytical sensors (dead code, test quality drift, dependency scanning) belong as scheduled jobs
- **Harness Regulation Categories**: Guides and sensors apply across three distinct quality concerns — (1) **Maintainability**: code structure, coverage, style, complexity; (2) **Architecture Fitness**: conformance to architectural constraints and fitness functions; (3) **Behaviour**: functional correctness. Behaviour is the hardest to harness — AI-generated test suites used as both guide and sensor create a circular quality argument
- **The Steering Loop**: The meta-level process of improving the harness itself. When a failure occurs repeatedly, the right response is to add or strengthen the guide that would have prevented it and the sensor that would have caught it — not just to retry. The harness improves over time by treating failures as permanent signal

## In Practice
Method harnesses follow a layered control structure. Computational sensors run on every tool invocation: typecheck after every edit, lint before every commit, tests before every PR. Inferential sensors run as CI pipeline steps: an LLM reviewer subagent flags architectural violations and anti-patterns on the diff. Guides are versioned alongside application code: CLAUDE.md and skill files are reviewed in PRs. When the same failure class appears twice, a new guide is added to prevent it and a new sensor is added to detect recurrence.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Harness Guides and Sensors**: Every harness failure has two remedies: a guide that makes the failure less likely and a sensor that catches it when it happens anyway. If you only have sensors, your agent will make the same mistakes repeatedly and self-correct them — which is expensive and unreliable. If you only have guides, you have rules without verification. Audit your harness by listing every failure mode you've seen and checking whether each has both a guide and a sensor. Silent sensors are either working perfectly or detecting nothing — you can't tell which without coverage metrics. → `engineering-knowledge-repository/harness-guides-and-sensors.md`

## Related Entries
- [Harness Engineering](harness-engineering.md) — guides and sensors are the primary control taxonomy within a harness
- [Agent Patterns](agent-patterns.md) — the ReAct loop is where sensors inject feedback and guides scope behavior
- [Evolutionary Architecture](evolutionary-architecture.md) — architecture fitness functions are a direct application of sensors to architectural conformance
- [CI/CD](ci-cd.md) — the timing layer for guides and sensors maps onto CI/CD pipeline stages
- [Mutation Testing](mutation-testing.md) — mutation testing is an inferential sensor for test suite quality
- [LLM Guardrails](llm-guardrails.md) — guardrails are a class of sensors applied to model output at the application boundary
- [LLM Observability](llm-observability.md) — observability provides the signal needed to detect when silent sensors indicate quality vs. inadequate detection

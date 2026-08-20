---
id: harness-engineering
tags: [pattern, ai-ml, architecture, agent, orchestration]
surfaces-at: [application-design, nfr-requirements, code-generation]
related: [agent-patterns, model-abstraction-layer, prompt-engineering, context-window-management, human-in-the-loop, multi-agent-systems, llm-observability, harness-guides-and-sensors, harnessability, autonomous-coding-loop, planner-generator-evaluator, haas]
complexity: intermediate
---

# Harness Engineering

## What It Is
A harness is a structured scaffolding layer that wraps an AI model and gives it the context, tools, constraints, and control flow it needs to operate reliably within a defined domain. Rather than calling a model ad hoc with raw prompts, harness engineering establishes the full execution environment: system prompt, available tools, memory access, output parsing, error handling, and feedback loops. The harness is the difference between a model that can answer a question and a model that can execute a workflow.

Claude Code, the AIDLC orchestration layer, and most production AI agents are harnesses — the model is the reasoning engine; the harness is everything else.

## When to Apply
- Any production AI application where a model must take actions, follow a multi-step workflow, or operate within defined constraints
- When the same model needs to behave differently across contexts (e.g., a delivery assistant vs. a code reviewer) — each context is a harness configuration
- When reliability, auditability, or compliance requirements apply to AI-driven behavior
- When multiple AI capabilities (tools, memory, retrieval, sub-agents) must be composed into a coherent system

## When Not to Apply
- Simple single-turn question-answer applications where no workflow execution or tool use is required
- Prototypes and spikes where raw prompt iteration speed matters more than structure
- When a higher-level harness framework (LangChain, LlamaIndex, Claude Code) already provides the scaffolding you need — build on it, don't reinvent it

## Key Concepts
- **System Prompt**: The harness's primary control surface. Defines the model's role, constraints, behavioral rules, output format, and what tools it may use. The system prompt is code — it should be versioned, reviewed, and tested like code
- **Tool Definitions**: The set of actions the model can invoke. Well-designed harnesses give models the minimum set of tools needed for the task — not every tool available. Tool sprawl increases error surface and token cost
- **Context Management**: Harnesses control what goes into the context window at each step: conversation history, retrieved documents, tool results, prior decisions. Context management is the primary lever for both cost control and model reliability — models perform better with focused context than with everything thrown at them
- **Output Parsing and Validation**: Models produce text; harnesses consume structured data. Reliable harnesses define output schemas, validate model responses against them, and handle malformed output gracefully — including retry logic for parsing failures
- **Memory Architecture**: Harnesses decide what to remember across turns (in-context), across sessions (persistent), and across agent invocations (shared). These are distinct problems with distinct solutions. Conflating them produces systems that are expensive, inconsistent, or both
- **Control Flow**: The harness owns the execution loop — deciding when to call the model, when to invoke tools, when to pause for human review, and when to terminate. The model advises on next steps; the harness decides whether to take them
- **Observability**: Every model call in a harness should emit: prompt token count, completion token count, latency, tool invocations, and outcome. You cannot optimize or debug what you cannot measure
- **Prompt Injection Defense**: Harnesses that process external input (user messages, retrieved documents, tool results) are vulnerable to prompt injection — adversarial content designed to override system prompt instructions. Defense requires input sanitization, output validation, and privileged/unprivileged context separation

## In Practice
Method builds harnesses as thin orchestration layers on top of a Model Abstraction Layer. The system prompt and tool definitions live in version-controlled files, not application code. Context assembly is a discrete, testable function. Output schemas are defined with Pydantic or Zod and validated before the result is acted on. Observability hooks are injected at the harness level, not scattered across callers.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Harness Engineering**: A model without a harness is a capability; a model with a harness is a system. The harness — system prompt, tools, context assembly, output parsing, control flow — is where correctness, reliability, and cost are actually determined. Treat the system prompt as code: version it, review it, test it. Keep tool sets minimal and purposeful — every extra tool is a decision the model has to make and a failure mode you have to handle. Own the control flow in your harness; don't let the model decide when to stop. → `engineering-knowledge-repository/harness-engineering.md`

## Related Entries
- [Agent Patterns](agent-patterns.md) — harnesses are the implementation substrate for agent patterns
- [Model Abstraction Layer](model-abstraction-layer.md) — harnesses call models through an abstraction layer, not directly
- [Prompt Engineering](prompt-engineering.md) — the system prompt is the harness's primary control surface
- [Context Window Management](context-window-management.md) — harnesses own context assembly and must manage window limits deliberately
- [Human in the Loop](human-in-the-loop.md) — harnesses implement HITL gates by pausing control flow at defined checkpoints
- [Multi-Agent Systems](multi-agent-systems.md) — multi-agent systems are composed harnesses; each agent is a harness; the orchestrator is another harness coordinating them
- [LLM Observability](llm-observability.md) — the harness is the natural instrumentation point for all LLM observability signals
- [Harness Guides and Sensors](harness-guides-and-sensors.md) — the feedforward/feedback control taxonomy for designing harness quality controls
- [Harnessability](harnessability.md) — properties of a codebase that make it tractable to agents operating through a harness
- [Autonomous Coding Loop](autonomous-coding-loop.md) — long-horizon execution pattern built on top of the harness loop controller
- [Planner-Generator-Evaluator](planner-generator-evaluator.md) — three-role agent decomposition pattern for quality-critical generation tasks
- [Harness-as-a-Service](haas.md) — managed harness runtime platforms that provide loop, tools, and context infrastructure

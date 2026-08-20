---
id: agent-patterns
tags: [pattern, ai-ml, backend, distributed-systems]
surfaces-at: [application-design, functional-design]
related: [ai-agent-architecture, multi-agent-systems, prompt-engineering, llm-observability, llm-guardrails, prompt-injection-defense, retrieval-augmented-generation]
complexity: advanced
---

# Agent Patterns

## What It Is
Architectures where an LLM acts as a reasoning engine that autonomously selects and executes tools (functions, APIs, searches) in a loop to complete a goal. Unlike a single prompt-response interaction, agents persist state, make decisions across multiple steps, and take actions with real-world consequences. The LLM decides what to do next based on available tools and prior results — continuing until the goal is achieved or a stopping condition is met.

## When to Apply
- Tasks too complex for a single LLM call — multi-step research, code generation with execution, data analysis
- Workflows requiring dynamic tool selection — the LLM decides which tools to use based on the task
- Automation of tasks that previously required human judgment across multiple systems

## When Not to Apply
- Simple single-step tasks where a direct prompt is sufficient — agents add latency and cost
- High-stakes irreversible actions without human confirmation — autonomous agents can make costly mistakes
- When deterministic, predictable behavior is required — agent reasoning is non-deterministic

## Key Concepts
- **Tool Use / Function Calling**: The LLM is given a set of tools (functions with descriptions and schemas). It decides which tool to call, with what arguments, and incorporates the result in subsequent reasoning. The foundation of all agent architectures
- **ReAct (Reasoning + Acting)**: A prompting pattern where the LLM interleaves reasoning (Thought) and action (Act) steps — `Thought: I need to find the current price → Act: search("current AAPL price") → Observation: $185 → Thought: Now I can answer`. Produces interpretable reasoning chains
- **Plan-and-Execute**: The agent first creates a plan (list of steps), then executes each step. More predictable than pure ReAct; struggles with dynamic plans that need to change mid-execution
- **Multi-Agent Systems**: Multiple specialized agents collaborating — an orchestrator agent delegates to specialist agents (researcher, coder, reviewer). Reduces context window pressure; adds coordination complexity
- **Memory**: Agents can have short-term memory (conversation history), long-term memory (vector store of past interactions), and working memory (scratchpad for current task). Memory management is critical for long-running agents
- **Agent Loop**: The core execution pattern — observe state → reason → select action → execute action → observe result → repeat. Continues until the goal is achieved, a max step limit is hit, or an error occurs
- **Max Iterations / Step Limit**: Prevent infinite loops by setting a maximum number of reasoning steps. Agents that don't terminate are a reliability and cost problem
- **Human-in-the-Loop**: For high-stakes actions, pause and request human approval before proceeding. The agent proposes; the human confirms
- **LangChain / LangGraph**: Popular frameworks for building agent systems — LangGraph adds explicit state machine control over agent execution flow
- **Observability is Non-Negotiable**: Multi-step agent execution must be traced end-to-end — every tool call, reasoning step, and intermediate result. Debugging without traces is impossible

## In Practice
Method agentic applications use function calling for tool integration, ReAct prompting for transparent reasoning, step limits (max 10-20 steps) to prevent runaway execution, and human confirmation gates for irreversible actions. LangGraph is used for complex multi-agent workflows requiring explicit state management. All agent traces are captured in LLM observability tooling.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Agent Patterns**: Agents are LLMs in a loop — they reason, use tools, observe results, and repeat. Use ReAct for transparent reasoning chains. Set a max step limit — unconstrained agents loop forever and cost money. Always add human confirmation before irreversible actions. Multi-agent systems reduce context pressure but add orchestration complexity — start with a single agent and add specialization when needed. Observability is mandatory: trace every reasoning step and tool call. Prompt injection risk is highest in agents — a successful injection can trigger real-world actions. → `engineering-knowledge-repository/agent-patterns.md`

## Related Entries
- [AI Agent Architecture](ai-agent-architecture.md) — foundational blueprint covering agent components, types, and architecture selection
- [Multi-Agent Systems](multi-agent-systems.md) — orchestration patterns, agent communication, and failure isolation for multi-agent networks
- [Prompt Engineering](prompt-engineering.md) — ReAct and tool use prompting are foundational to agent design
- [LLM Observability](llm-observability.md) — tracing agent execution is a production requirement
- [LLM Guardrails](llm-guardrails.md) — agents acting on the world need guardrails before taking irreversible actions
- [Prompt Injection Defense](prompt-injection-defense.md) — injection in agentic systems can trigger real-world actions
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — search/retrieval is a common agent tool

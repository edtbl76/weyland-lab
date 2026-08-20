---
id: multi-agent-systems
tags: [architecture, ai-ml, backend, distributed-systems]
surfaces-at: [application-design, functional-design]
related: [ai-agent-architecture, agent-patterns, llm-observability, llm-guardrails, prompt-injection-defense, choreography-vs-orchestration, context-window-management]
complexity: advanced
---

# Multi-Agent Systems

## What It Is
Collaborative frameworks where multiple specialized AI agents interact to solve tasks that are too complex, too long, or too broad for a single agent to handle alone. Each agent in a multi-agent system (MAS) has a defined role — planner, researcher, coder, reviewer, critic — and communicates with other agents through structured messages or shared state. The system as a whole can exceed the capability of any individual agent by parallelizing work, distributing specialized knowledge, and breaking tasks across context window boundaries. The tradeoff: coordination complexity increases proportionally with agent count, and failures in one agent can cascade through the system.

## When to Apply
- Tasks that exceed a single context window — long documents, multi-phase research, large codebases
- Workflows with distinct specialized subtasks that benefit from dedicated models or prompts per role
- Parallelizable work — multiple agents working concurrently on independent sub-problems
- When a single agent's error rate is too high and peer review by a second agent improves reliability
- Complex reasoning chains requiring planning, execution, and critique as distinct phases

## When Not to Apply
- Tasks a single agent handles reliably — multi-agent adds latency, cost, and coordination overhead without benefit
- When inter-agent communication errors would be harder to debug than single-agent failures
- Tight latency requirements — agent-to-agent calls add round trips; sequential MAS can be significantly slower than a single-agent equivalent

## Key Concepts

### Coordination Patterns

- **Orchestrator / Manager Pattern**: A central orchestrator agent receives the task, decomposes it into subtasks, delegates each to a specialized worker agent, monitors completion, handles failures, and assembles the final result. The orchestrator does not do domain work directly — it routes and consolidates. Equivalent to the manager in an organization: strategic direction, delegation, quality control. This is the most common production MAS pattern
- **Planner-Worker Pattern**: A planning agent first produces a structured plan (list of steps with assigned agents); worker agents execute each step in sequence or in parallel. The plan is explicit and inspectable — unlike pure ReAct where planning is implicit in the reasoning trace. Useful when the task structure can be determined upfront
- **Peer-to-Peer / Collaborative**: Agents communicate directly without a central orchestrator — passing messages, sharing intermediate results, or negotiating on outputs. More flexible but harder to reason about; debugging requires tracing across multiple agents simultaneously. Rare in production LLM systems
- **Critic / Reviewer Pattern**: A dedicated critic agent evaluates the output of a primary agent — checking for errors, hallucinations, missing steps, or policy violations — before the output is accepted. Acts as a second opinion. Particularly effective when the primary agent's failure mode is confident-but-wrong output
- **Blackboard Architecture**: Agents share a common workspace (the "blackboard") where they post observations and results that other agents can read and build upon. No direct agent-to-agent communication — coordination happens through shared state. Useful for document annotation, incremental analysis, and multi-perspective synthesis

### Agent Specialization

Agents in a MAS are specialized by role, and each role typically has a tailored system prompt and sometimes a different model:
- **Planner**: Decomposes the high-level goal into a structured task list; assigns tasks to appropriate agents; replans when subtasks fail
- **Researcher / Retrieval Agent**: Searches the web, internal knowledge bases, or databases; returns retrieved evidence without interpretation
- **Executor / Worker Agent**: Performs domain-specific work — writing code, drafting content, running analysis — against a specific subtask
- **Critic / Evaluator Agent**: Reviews worker outputs for correctness, coherence, policy compliance, or quality; returns pass/fail with specific feedback
- **Summarizer Agent**: Condenses outputs from multiple workers into a coherent final result; handles synthesis across long accumulated context

### Communication and State

- **Structured Message Passing**: Agents communicate via typed, schema-validated messages rather than freeform text. Schemas prevent misinterpretation between agents — an orchestrator that sends a task and receives a result must agree on the format with its workers. JSON schemas are the standard
- **Shared State Store**: A persistent object (database, in-memory store, or LangGraph state) shared across agents. Each agent reads from and writes to state. Enables agents to pick up where another left off. LangGraph's state graph is the most common implementation
- **Context Passing vs. State Store**: Passing full context between agents via messages is simple but token-expensive. A shared state store is more efficient but requires all agents to have access to the same persistence layer
- **Task Queues**: In async multi-agent systems, tasks are placed on a queue; worker agents pull from the queue rather than being invoked directly by the orchestrator. Enables parallelism and retry logic without tight coupling

### Failure Isolation and Reliability

- **Per-Agent Step Limits**: Each agent should have its own max iteration limit, independent of the system's overall limit. An agent that loops indefinitely blocks the orchestrator and can exhaust token budgets for the entire system
- **Retry and Fallback**: The orchestrator should implement retry logic for failed worker agents — with backoff, an alternative agent, or a simplified subtask. Define what constitutes failure (timeout, error, low-confidence output) before deployment
- **Graceful Degradation**: Design the system to return a partial result when some agents fail rather than failing completely. Distinguish between critical agents (failure blocks the whole task) and optional agents (failure reduces quality but doesn't block completion)
- **Idempotent Tool Calls**: Worker agents that call external tools should be designed so repeated calls (due to retry) do not produce duplicate side effects — database writes, emails sent, API mutations. See [Idempotency](idempotency.md)

### Trust and Security

- **Inter-Agent Trust Boundaries**: Agents should not blindly trust inputs from other agents — particularly in systems where an external user can influence agent-to-agent messages. A compromised worker agent can send a malicious instruction to the orchestrator. Validate inter-agent messages the same way you validate user input
- **Prompt Injection Across Agents**: A user-controlled input that reaches a sub-agent can inject instructions that propagate through the agent network. Sanitize untrusted content before it enters any agent's context. See [Prompt Injection Defense](prompt-injection-defense.md)
- **Principle of Least Capability**: Each agent should have access only to the tools and data it needs for its specific role. A research agent does not need write access; a summarizer does not need external API access. Reduces blast radius if an agent is compromised or misbehaves

### Observability

Multi-agent systems are substantially harder to debug than single agents. Failures can occur in any agent, any inter-agent message, or any shared state transition — and root cause tracing requires end-to-end visibility:
- Trace IDs must propagate through all agent calls — every message, tool call, and state write should carry the parent trace ID
- Log the full input and output of every agent invocation, not just the final system output
- Track which agent produced which part of the final output — enables attribution when the output is partially wrong
- See [LLM Observability](llm-observability.md) for instrumentation patterns

## In Practice
Method multi-agent implementations use LangGraph for explicit state management across agents. The orchestrator pattern is the default: one orchestrator, two to five specialized worker agents, one critic agent for output review. Agent communication uses typed Pydantic schemas. Each agent has a 10-step max limit; the orchestrator has a 30-step limit. Prompt injection defense is applied at every boundary where user-controlled input enters the agent network. All agent spans are traced with parent-child trace IDs in the LLM observability pipeline.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Multi-Agent Systems**: Use multi-agent when a single agent can't fit the task in one context window, or when specialization genuinely improves quality. Default to the orchestrator pattern — it's the most debuggable. Specialize agents by role with tailored system prompts; consider different models per role (a small model for classification, a large model for generation). Every agent boundary is a trust boundary — validate inter-agent messages. Set per-agent step limits independently of the system limit. Trace everything with propagated trace IDs or you won't be able to debug production failures. Don't add agents for their own sake — each agent added multiplies coordination complexity, latency, and cost. → `engineering-knowledge-repository/multi-agent-systems.md`

## Related Entries
- [AI Agent Architecture](ai-agent-architecture.md) — foundational agent concepts: components, types, and pattern selection that multi-agent systems are built on
- [Agent Patterns](agent-patterns.md) — implementation patterns within individual agents (ReAct, Plan-and-Execute, tool use) that compose into multi-agent systems
- [LLM Observability](llm-observability.md) — end-to-end tracing across agent boundaries is a production requirement for multi-agent systems
- [LLM Guardrails](llm-guardrails.md) — each agent in the network needs independent output validation before passing results to the next agent
- [Prompt Injection Defense](prompt-injection-defense.md) — injection risk multiplies in multi-agent systems; a successful injection in one agent can propagate instructions through the network
- [Choreography vs. Orchestration](choreography-vs-orchestration.md) — the orchestrator pattern is the centralized form; peer-to-peer MAS is the choreographed form; the same tradeoffs apply
- [Context Window Management](context-window-management.md) — agent specialization exists partly to manage context window pressure; each agent maintains a focused window over its specific subtask

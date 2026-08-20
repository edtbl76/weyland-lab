---
id: haas
tags: [pattern, ai-ml, agent, platform, architecture, orchestration]
surfaces-at: [application-design, nfr-requirements, requirements-analysis]
related: [harness-engineering, model-abstraction-layer, agent-patterns, multi-agent-systems, build-vs-buy, autonomous-coding-loop, planner-generator-evaluator]
complexity: intermediate
---

# Harness-as-a-Service (HaaS)

## What It Is
Harness-as-a-Service (HaaS) is the architectural shift from building AI applications on raw LLM completion APIs to building on harness runtime APIs — platforms that provide the agent loop, tool execution, context management, memory, sandboxing, and subagent orchestration as managed infrastructure. The application developer configures the harness rather than implementing it: they define system prompts, tools, subagents, and hooks; the HaaS runtime handles loop state, context lifecycle, tool dispatch, and failure recovery.

The term was coined by Viv Trivedy as a framing for the direction of the agent platform market. Examples of HaaS platforms include the Claude Agent SDK, OpenAI Agents SDK, and Codex SDK. The shift parallels the move from bare-metal servers to cloud infrastructure — in both cases, the managed layer handles operational complexity that was previously the application developer's responsibility.

The practical implication: teams building AI-powered applications no longer need to choose between "use a raw completion API and build everything" and "use a vendor product and accept all its opinions." HaaS platforms offer a middle path — managed infrastructure with a configuration surface.

## When to Apply
- Building new AI-powered applications or agents where the agent loop, tool execution, and context management would otherwise need to be built from scratch
- Evaluating whether to build a custom harness vs. build on a managed harness platform — the HaaS framing clarifies the tradeoff
- Selecting an agent framework or platform — understanding HaaS characteristics helps assess what a platform actually manages vs. what it leaves to you
- Designing the platform layer for a multi-team AI development organization — internal HaaS platforms enable teams to share harness infrastructure and configuration conventions

## When Not to Apply
- Simple single-turn completion applications with no agent loop — HaaS overhead is unjustified
- Applications with strict vendor-independence requirements where adopting a HaaS platform creates unacceptable lock-in
- Cases where the application's requirements are fundamentally incompatible with available HaaS platforms — custom harness is the right answer, not a workaround

## Key Concepts
- **Harness Runtime**: The managed infrastructure a HaaS platform provides. Typically includes: the agent loop (iteration, continuation, stopping logic), tool registry and dispatch, context window management (compaction, summarization), session state, subagent spawning and coordination, and observability hooks. This is what the application developer does not have to build
- **Configuration Surface**: The four primary dimensions an application developer controls in a HaaS platform: (1) **System Prompt** — role definition, constraints, behavioral rules; (2) **Tools** — available actions and their schemas; (3) **Context Policy** — what gets loaded, when, and in what order; (4) **Subagent Topology** — how sub-tasks are decomposed and delegated. Everything else is runtime responsibility
- **From Completion API to Runtime API**: A raw LLM API gives you a completion — tokens in, tokens out. A HaaS runtime gives you an execution environment — goals in, verified results out (or an error with history). The abstraction level shift is significant: the application developer reasons about tasks and tools, not about token counts and context window management
- **Skill and Tool Ecosystem**: HaaS platforms typically offer a marketplace or registry of pre-built skills and tool integrations (filesystem, browser, MCP servers, code execution sandboxes). The application developer assembles a harness from these primitives rather than implementing them. This is analogous to NPM packages for application code — reuse of validated primitives rather than reinvention
- **Build vs. HaaS Tradeoff**: Custom harnesses offer maximum control and no platform dependency. HaaS platforms offer faster time-to-value, maintained infrastructure, and access to platform-level improvements (better compaction, new tool primitives, improved subagent coordination). The right choice depends on: task complexity, required customization depth, team capacity, and vendor lock-in tolerance. The Model Abstraction Layer pattern mitigates HaaS lock-in by keeping model and runtime dependencies behind an interface
- **Post-Training Coupling**: HaaS platforms and their underlying models are often co-trained — the model is post-trained to perform well with the platform's specific harness primitives. This means moving a model from its native HaaS environment to a custom harness may degrade performance even if the model "should" be capable of the task. Understanding post-training coupling informs both harness selection and migration planning
- **Internal HaaS**: Large organizations building multiple AI-powered applications may develop internal HaaS platforms — shared harness infrastructure, common tool libraries, and standardized configuration conventions used across teams. This captures the reuse benefits of HaaS without external vendor dependency and enables organization-wide observability and governance

## In Practice
Method evaluates HaaS platforms at the start of AI-powered application engagements using a build/buy/partner framework applied specifically to the harness layer. Assessment criteria: required customization depth (does the application need harness behaviors the platform doesn't support?), platform maturity and observability, lock-in risk and mitigation options (Model Abstraction Layer), and total cost compared to custom harness development. For most client engagements, building on a HaaS platform is the right starting point; custom harness development is reserved for cases with unique requirements or vendor-incompatible constraints.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Harness-as-a-Service**: The default path for a new AI agent application is now: pick a HaaS platform, configure it along four dimensions (system prompt, tools, context policy, subagent topology), and put your engineering effort into domain-specific prompt and tool design — not into reimplementing the loop, context management, and tool dispatch infrastructure. Building a custom harness from scratch is a significant engineering investment that's only justified when available platforms genuinely cannot meet your requirements. Evaluate HaaS platforms the same way you evaluate any managed service: what does it actually manage, what does it leave to you, and what does adopting it cost you in optionality? → `engineering-knowledge-repository/haas.md`

## Related Entries
- [Harness Engineering](harness-engineering.md) — HaaS provides the harness runtime; harness engineering is the discipline of configuring and extending it
- [Model Abstraction Layer](model-abstraction-layer.md) — model abstraction reduces HaaS lock-in by decoupling application logic from the specific platform and model
- [Agent Patterns](agent-patterns.md) — HaaS platforms implement agent patterns as managed infrastructure; understanding the patterns informs platform selection and configuration
- [Multi-Agent Systems](multi-agent-systems.md) — HaaS platforms typically provide subagent spawning and coordination; multi-agent system design applies to configuring these features
- [Build vs. Buy](build-vs-buy.md) — the decision to use a HaaS platform vs. build a custom harness is a build/buy decision at the harness layer
- [Autonomous Coding Loop](autonomous-coding-loop.md) — HaaS platforms provide the loop controller and state management that autonomous coding loops require
- [Planner-Generator-Evaluator](planner-generator-evaluator.md) — HaaS subagent primitives are the infrastructure for implementing the three-role pattern

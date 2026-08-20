---
id: llm-observability
tags: [tooling, ai-ml, observability, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [opentelemetry, distributed-tracing, metrics-and-alerting, llm-cost-optimization, llm-evaluation, agent-patterns]
complexity: intermediate
---

# LLM Observability

## What It Is
The instrumentation, tracing, and monitoring of LLM application behavior in production. Traditional observability (metrics, logs, traces) is necessary but insufficient for LLM systems — you also need to capture prompts, responses, token counts, model versions, retrieval results, latency per step, and quality signals. LLM observability makes complex multi-step pipelines (RAG, agents) debuggable, enables cost attribution, and surfaces quality drift over time.

## When to Apply
- Before any LLM application goes to production — observability must be in place at launch, not added after
- For every LLM call in the application — uninstrumented calls are black boxes

## Key Concepts
- **Trace**: The complete record of a single LLM request — every prompt, tool call, retrieval step, and response in the execution chain. Essential for debugging multi-step agent workflows
- **Span Attributes for LLM**: Alongside standard span data, capture: model name, prompt tokens, completion tokens, cost, temperature, top-p, finish reason, and application-defined metadata (user ID, session ID, feature name)
- **Prompt and Response Logging**: Store the full prompt and response for every LLM call. Required for debugging, evaluation, and fine-tuning data collection. PII must be redacted before logging
- **Token Usage Metrics**: Track prompt tokens, completion tokens, and total cost per request and per feature/user. Token usage is the primary cost driver and a leading indicator of latency issues
- **Latency Breakdown**: For RAG and agent pipelines, measure latency per step — embedding time, retrieval time, LLM inference time, guardrail check time. Identify bottlenecks at the step level
- **Quality Signals**: Capture user feedback (thumbs up/down, explicit ratings), downstream outcomes (did the user rephrase? did they abandon?), and automated quality scores from guardrail evaluators
- **LangSmith**: LangChain's observability platform — auto-instruments LangChain/LangGraph pipelines, provides trace visualization, prompt versioning, and eval dataset management
- **Helicone**: Proxy-based LLM observability — sits between your application and the LLM API, captures all calls without code changes. Supports cost tracking and caching
- **OpenTelemetry for LLMs**: The OpenTelemetry semantic conventions for LLM spans are emerging — `gen_ai.*` attributes. Enables vendor-neutral LLM tracing via standard OTEL exporters
- **Feedback Loop**: Production traces feed back into the evaluation dataset — interesting failures become new golden set examples. This closes the quality improvement loop

## In Practice
Method LLM applications are instrumented with LangSmith (for LangChain-based apps) or direct OTEL instrumentation. Every LLM call captures model, token counts, latency, and cost. Full prompt/response logging is enabled with PII redaction. Cost dashboards are built in Grafana from token usage metrics. Quality alerts trigger when error rates or guardrail failure rates exceed thresholds.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — LLM Observability**: Instrument before you launch. For every LLM call, capture: model, tokens (prompt + completion), cost, latency, and the full prompt/response (with PII redacted). For RAG and agents, trace every step — you cannot debug a black box pipeline. Surface token cost per feature so you can optimize the expensive ones. Collect user feedback signals — they're ground truth for quality. Feed production failures back into your eval dataset. Use LangSmith, Helicone, or OTEL `gen_ai.*` conventions depending on your stack. → `engineering-knowledge-repository/llm-observability.md`

## Related Entries
- [OpenTelemetry](opentelemetry.md) — the vendor-neutral instrumentation standard, now with LLM semantic conventions
- [Distributed Tracing](distributed-tracing.md) — LLM traces are distributed traces across prompt/retrieval/generation steps
- [Metrics and Alerting](metrics-and-alerting.md) — token usage, cost, and quality metrics feed the alerting pipeline
- [LLM Cost Optimization](llm-cost-optimization.md) — observability data identifies cost optimization opportunities
- [LLM Evaluation](llm-evaluation.md) — production traces feed back into offline evaluation datasets
- [Agent Patterns](agent-patterns.md) — agent execution chains require step-level tracing to be debuggable

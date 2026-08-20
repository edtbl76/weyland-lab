---
id: llm-cost-optimization
tags: [methodology, ai-ml, cost, backend]
surfaces-at: [nfr-requirements, application-design]
related: [llm-caching, context-window-management, llm-observability, model-serving, online-vs-batch-inference]
complexity: intermediate
---

# LLM Cost Optimization

## What It Is
Strategies for reducing the financial cost of running LLM applications in production. LLM API costs can scale rapidly — a poorly optimized application at moderate traffic can cost thousands of dollars per day. Cost is driven by token consumption (input + output tokens) and model tier. Optimization strategies range from caching and prompt compression to model routing and batch inference.

## When to Apply
- Before production launch — cost optimization is easiest when designed in, not retrofitted
- When cost per request exceeds budget targets
- As part of regular operational review

## Key Concepts
- **Token Cost Awareness**: Understand what drives cost — input tokens (prompt + context) × input price + output tokens × output price. Output tokens are typically 2-5x more expensive than input tokens. Measure cost per feature, per user, and per query type
- **Model Tiering / Routing**: Use smaller, cheaper models for simple tasks (classification, extraction, summarization) and larger models only for complex reasoning. GPT-4o-mini vs GPT-4o; Haiku vs Sonnet vs Opus. Route based on query complexity — saves 80-90% on simple queries
- **Caching**: The highest-ROI optimization. Exact caching for repeated identical queries. Semantic caching for near-duplicate queries. Provider-side prompt caching for stable system prompts. See LLM Caching
- **Prompt Compression**: Reduce token count in prompts without losing information. Techniques: removing redundant instructions, compressing few-shot examples, using LLMLingua for automated compression
- **Output Length Control**: Instruct the model to be concise. `"Respond in 2-3 sentences maximum."` Output tokens are expensive — unbounded output is a cost risk
- **Batch Inference**: For non-real-time workloads, use async batch APIs (OpenAI Batch API, Anthropic Batch). Typically 50% cheaper than synchronous calls. Process document analysis, classification, and embeddings overnight
- **Streaming**: Streaming responses don't reduce token cost but improve perceived latency — users see output immediately rather than waiting for the full response. Does not save money; saves user experience
- **Provider-Side Prompt Caching**: Anthropic and OpenAI cache repeated prompt prefixes (system prompts, large documents) at ~90% cost reduction for cached tokens. Structure prompts to maximize the stable prefix
- **Embedding Cost**: Embedding is much cheaper than generation but adds up at scale. Cache embeddings for stable documents — don't re-embed on every query. Use smaller embedding models where retrieval quality allows
- **Budget Alerts**: Set cost alerts at 50%, 80%, and 100% of budget. Implement hard limits per user/session to prevent runaway costs from bugs or abuse

## In Practice
Method LLM applications implement model tiering (route simple tasks to cheaper models), provider-side prompt caching (stable system prompts), output length constraints, and batch processing for offline workloads. Cost per query is measured by feature and tracked in dashboards. Budget alerts are configured in the LLM provider console and in application monitoring.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — LLM Cost Optimization**: Measure first — instrument token usage per feature before optimizing. Then apply in order of ROI: (1) caching (highest ROI), (2) model tiering (use smaller models for simple tasks), (3) provider-side prompt caching for stable prefixes, (4) output length constraints, (5) batch inference for non-real-time workloads. Output tokens cost 2-5x more than input tokens — constrain output length explicitly. Set budget alerts and per-user hard limits. Cost optimization and quality are not always in conflict — smaller models are often sufficient for classification and extraction tasks. → `engineering-knowledge-repository/llm-cost-optimization.md`

## Related Entries
- [LLM Caching](llm-caching.md) — the highest-ROI cost reduction technique
- [Context Window Management](context-window-management.md) — smaller context = fewer input tokens = lower cost
- [LLM Observability](llm-observability.md) — cost visibility requires instrumenting every LLM call
- [Model Serving](model-serving.md) — self-hosted model serving trades API cost for infrastructure cost
- [Online vs. Batch Inference](online-vs-batch-inference.md) — batch inference is 50% cheaper for non-real-time workloads

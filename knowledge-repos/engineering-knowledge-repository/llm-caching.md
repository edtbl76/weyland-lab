---
id: llm-caching
tags: [pattern, ai-ml, backend, performance]
surfaces-at: [application-design, nfr-requirements, infrastructure-design]
related: [caching-strategies, llm-cost-optimization, semantic-search, prompt-engineering, context-window-management]
complexity: intermediate
---

# LLM Caching

## What It Is
Strategies for storing and reusing LLM outputs to reduce API cost, latency, and rate limit pressure. LLM API calls are expensive (cents per request at scale) and slow (1-30 seconds). Many production workloads generate repeated or near-identical queries — caching these responses can reduce costs by 30-80%. There are two distinct caching strategies: exact caching (identical input → cached output) and semantic caching (similar input → cached output).

## When to Apply
- Any LLM application where cost or latency is a concern
- Workloads with high query repetition (FAQ bots, document Q&A, product search)
- Applications with predictable, static prompt components

## Key Concepts
- **Exact Caching**: Hash the complete prompt (system + history + user message); cache the response. Fast, zero false positives. Works when identical prompts recur — common in structured workflows and API use cases
- **Semantic Caching**: Embed the user query, search a cache of past queries by semantic similarity, return cached response if similarity exceeds a threshold. Handles near-duplicate queries ("What's the return policy?" vs "How do I return an item?"). GPTCache and Redis with vector search implement this pattern
- **Cache Key Design**: For exact caching, the cache key is typically a SHA-256 hash of the normalized prompt. Normalize before hashing — strip whitespace, lowercase user input where appropriate
- **TTL Strategy**: LLM responses can become stale if the underlying knowledge changes. Set TTL based on knowledge volatility — static FAQs can cache for days; dynamic data should cache for minutes or not at all
- **Provider-Side Prompt Caching**: Anthropic, OpenAI, and Google offer prompt caching for repeated prefix tokens (system prompts, large documents). Prefix tokens sent repeatedly are cached server-side at a discount (~90% cost reduction for cached tokens). Use cache breakpoints to mark stable prefix boundaries
- **Semantic Cache Threshold Tuning**: Too high a similarity threshold → low hit rate. Too low → wrong answers returned. Tune empirically; start at 0.95 cosine similarity and adjust based on false positive/negative rates
- **Non-Determinism**: LLMs with temperature > 0 produce different outputs for the same input. Cache a single response per unique input — acceptable for most use cases; problematic if response variety is valuable
- **Cache Invalidation**: When the system prompt changes (new instructions, new knowledge), cached responses based on the old prompt are stale — flush or segment the cache by prompt version

## In Practice
Method LLM applications use exact caching (Redis, 24-hour TTL) for structured workflows where identical prompts recur. Provider-side prompt caching is enabled for all applications with large, stable system prompts or document prefixes. Semantic caching is added for user-facing Q&A applications with high query volume. Cache hit rates are monitored as a cost and performance metric.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — LLM Caching**: Cache aggressively — LLM calls are expensive and slow. Start with exact caching (hash the prompt, store in Redis with TTL). Enable provider-side prompt caching for stable system prompts — Anthropic and OpenAI cache repeated prefix tokens at ~90% cost reduction. Add semantic caching for user-facing queries where near-duplicate questions are common. Tune similarity threshold empirically — false positives (wrong cached answer) are worse than cache misses. Segment cache by prompt version to avoid serving stale responses after prompt updates. → `engineering-knowledge-repository/llm-caching.md`

## Related Entries
- [Caching Strategies](caching-strategies.md) — general caching patterns that apply to LLM response caching
- [LLM Cost Optimization](llm-cost-optimization.md) — caching is the highest-ROI LLM cost reduction technique
- [Semantic Search](semantic-search.md) — semantic caching uses embedding similarity to find cached responses
- [Prompt Engineering](prompt-engineering.md) — stable, well-structured prompts maximize provider-side cache hit rates
- [Context Window Management](context-window-management.md) — cached prefixes reduce effective context window consumption

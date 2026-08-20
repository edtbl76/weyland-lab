---
id: context-window-management
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [prompt-engineering, retrieval-augmented-generation, llm-cost-optimization, llm-caching]
complexity: intermediate
---

# Context Window Management

## What It Is
Strategies for fitting the right information into an LLM's context window — the maximum number of tokens a model can process in a single request. Context windows range from 4k tokens (older models) to 200k+ tokens (Claude, Gemini). Larger windows enable more context but increase latency and cost proportionally. Context window management is about maximizing the signal-to-noise ratio of what you put in the window, not just fitting everything.

## When to Apply
- Multi-turn conversations that accumulate history
- RAG systems where retrieved chunks compete for window space
- Document processing where inputs exceed the context limit
- Any application where token cost and latency are significant

## Key Concepts
- **Tokens vs. Words**: Tokens are sub-word units — roughly 0.75 words per token in English. A 4096-token window holds ~3000 words. Count tokens with `tiktoken` (OpenAI) before assuming content fits
- **Context Stuffing Anti-Pattern**: Including everything available in the context regardless of relevance — wastes tokens, dilutes the model's attention, increases cost and latency. More context is not always better
- **Sliding Window**: For long conversations or documents, maintain a rolling window of recent content — drop the oldest turns/chunks as new ones arrive. Simple; loses early context
- **Conversation Summarization**: Periodically summarize older conversation turns into a compact summary, replacing the raw history. Preserves key information while freeing window space
- **Hierarchical Summarization**: For very long documents, recursively summarize chunks, then summarize the summaries. Enables processing of book-length content
- **Selective Retrieval**: In RAG, retrieve only the most relevant chunks rather than including the entire corpus. Top-k retrieval keeps context focused
- **Lost in the Middle**: Research finding that LLMs attend less reliably to information in the middle of long contexts — place the most critical information at the beginning or end of the prompt
- **Token Budget Allocation**: Explicitly budget tokens across prompt components: system prompt (fixed), conversation history (variable), retrieved context (variable), user message, output reservation. Monitor each component's token usage
- **Prompt Compression**: Techniques to reduce token count without losing information — LLMLingua and similar tools extract the most information-dense parts of long prompts

## In Practice
Method LLM applications instrument token usage per component (system prompt, history, context, user message). Conversation history is summarized after 10 turns. RAG retrieves top-5 chunks with re-ranking to maximize relevance density. Critical instructions are placed at the start of the system prompt, not buried in the middle. Token budgets are monitored in production via LLM observability tooling.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Context Window Management**: More context is not always better — irrelevant content dilutes attention and increases cost. Budget your tokens explicitly: system prompt + history + retrieved context + user message must sum to less than the limit. Summarize conversation history rather than growing it indefinitely. In RAG, retrieve the most relevant chunks, not all chunks. Place critical instructions at the start of the prompt (lost-in-the-middle effect). Monitor token usage per component in production — it's a key cost and quality lever. → `engineering-knowledge-repository/context-window-management.md`

## Related Entries
- [Prompt Engineering](prompt-engineering.md) — context window management is part of deliberate prompt design
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — RAG chunk retrieval must fit within context window budget
- [LLM Cost Optimization](llm-cost-optimization.md) — token count directly drives API cost
- [LLM Caching](llm-caching.md) — caching reduces repeat context window consumption

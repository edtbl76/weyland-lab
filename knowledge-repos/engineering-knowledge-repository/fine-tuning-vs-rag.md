---
id: fine-tuning-vs-rag
tags: [reference, ai-ml, backend]
surfaces-at: [application-design, nfr-requirements, requirements-analysis]
related: [retrieval-augmented-generation, fine-tuning, transfer-learning, embeddings, prompt-engineering]
complexity: intermediate
---

# Fine-Tuning vs. RAG

## What It Is
A decision framework for choosing between two primary approaches to adapting a base LLM for a specific task or knowledge domain: Retrieval-Augmented Generation (RAG), which injects knowledge at inference time, versus fine-tuning, which bakes knowledge or behavior into the model's weights during training. They are not mutually exclusive — combined architectures are common — but the choice of primary strategy has significant implications for cost, maintainability, latency, and quality.

## When to Apply
- At the start of any LLM feature design — this decision shapes the entire architecture
- When a base model's outputs are insufficient and you need to decide why and how to improve them

## Key Concepts

**Use RAG when**:
- The problem is **knowledge injection** — the model needs access to documents it wasn't trained on
- The knowledge changes frequently — RAG updates are instant (re-index); fine-tuning requires retraining
- You need **source attribution** — RAG can cite the retrieved documents
- You need to reduce hallucination on domain-specific facts
- You want to start quickly — RAG can be production-ready in days; fine-tuning takes weeks

**Use Fine-Tuning when**:
- The problem is **style, tone, or format** — making the model respond in a specific way consistently
- You need the model to learn a task that can't be expressed in a prompt (complex reasoning patterns, specialized output schemas)
- Latency is critical — fine-tuned models don't have a retrieval step
- You want to **compress knowledge** into the model for offline or edge deployment
- The knowledge set is stable and large enough to train on

**Use Both when**:
- You need both knowledge injection (RAG) AND consistent behavior/format (fine-tuning)
- A fine-tuned model that is better at using retrieved context

**Decision Matrix**:
| Need | RAG | Fine-Tuning |
|---|---|---|
| Domain knowledge | ✓ | ✓ (static only) |
| Updatable knowledge | ✓ | ✗ |
| Source attribution | ✓ | ✗ |
| Style/tone adaptation | ✗ | ✓ |
| Low latency | ✗ | ✓ |
| Low cost to start | ✓ | ✗ |
| Offline/edge deployment | ✗ | ✓ |

- **Prompt Engineering First**: Before either RAG or fine-tuning, exhaust prompt engineering. Many quality problems are solved by better prompts at zero infrastructure cost
- **Fine-Tuning Cost**: Fine-tuning requires labeled training data, GPU compute, and ongoing retraining as the model or knowledge evolves. RAG requires embedding infrastructure and a vector store — lower upfront cost
- **Catastrophic Forgetting**: Fine-tuning on a narrow dataset can degrade the model's general capabilities. RAG leaves the base model intact

## In Practice
Method's default LLM architecture is RAG-first: prompt engineer the base model, then add retrieval if knowledge injection is needed. Fine-tuning is introduced only when RAG + prompting cannot achieve required behavior — typically for consistent output format, specialized domain reasoning, or latency-sensitive inference.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Fine-Tuning vs. RAG**: Default to prompt engineering → RAG → fine-tuning, in that order. RAG is the right tool for knowledge injection — it's updatable, attributable, and faster to build. Fine-tuning is the right tool for style, format, and behavior that can't be expressed in a prompt. The two are complementary — a fine-tuned model that is better at following RAG prompts is a valid architecture. Never fine-tune when better prompting would solve the problem. → `engineering-knowledge-repository/fine-tuning-vs-rag.md`

## Related Entries
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — the RAG architecture this entry compares against fine-tuning
- [Fine-Tuning](fine-tuning.md) — the fine-tuning process in detail
- [Transfer Learning](transfer-learning.md) — fine-tuning is a form of transfer learning
- [Embeddings](embeddings.md) — RAG relies on embeddings; fine-tuning changes the model weights instead
- [Prompt Engineering](prompt-engineering.md) — the first step before RAG or fine-tuning

---
id: prompt-engineering
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design, code-generation]
related: [retrieval-augmented-generation, llm-evaluation, llm-guardrails, context-window-management, few-shot-learning, agent-patterns, structured-prompt-driven-development, reasons-canvas]
complexity: intermediate
---

# Prompt Engineering

## What It Is
The practice of designing and structuring inputs to language models to produce reliable, accurate, and useful outputs. Prompts are the primary interface between applications and LLMs — small changes in phrasing, structure, and context can dramatically affect output quality. Prompt engineering is part craft, part systematic experimentation, and increasingly a formal discipline with documented techniques.

## When to Apply
- Every LLM-powered feature — even "simple" use cases benefit from deliberate prompt design
- Before fine-tuning — prompting is cheaper and faster; exhaust prompting approaches first
- When LLM outputs are inconsistent, hallucinating, or not following the desired format

## Key Concepts
- **System Prompt**: Instructions that define the model's role, constraints, and output format. Persistent across the conversation. The foundation of every LLM application: `"You are a helpful assistant that answers only questions about our product. Always respond in JSON."`
- **Few-Shot Prompting**: Including examples of the desired input-output behavior in the prompt. 3-5 examples dramatically improve consistency for structured output tasks
- **Zero-Shot Prompting**: No examples — relying on the model's pre-trained knowledge. Works for general tasks; less reliable for domain-specific or structured output
- **Chain-of-Thought (CoT)**: Instructing the model to reason step-by-step before answering — `"Think step by step."` Improves accuracy on reasoning and math tasks
- **Structured Output**: Requesting JSON, XML, or a specific schema in the system prompt. Combined with JSON mode (OpenAI) or grammar-constrained decoding to guarantee parseable output
- **Prompt Templates**: Parameterized prompt strings where variables (user input, retrieved context, history) are injected at runtime. The template is the unit of version control and testing
- **Temperature**: Controls randomness — low (0.0–0.3) for deterministic tasks (classification, extraction), high (0.7–1.0) for creative tasks. A critical parameter alongside the prompt
- **Role Prompting**: Assigning a persona — `"You are a senior security engineer reviewing this code."` Activates relevant model knowledge and tone
- **Prompt Injection Risk**: User input incorporated into prompts can override system instructions. Treat user input as untrusted data — see Prompt Injection Defense

## In Practice
Method LLM applications use versioned prompt templates stored in code (not hardcoded inline). System prompts define role, constraints, and output format. Few-shot examples are included for extraction and classification tasks. Chain-of-thought is used for reasoning tasks. Prompt changes go through the same review process as code changes — they affect production behavior.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Prompt Engineering**: The system prompt is the most important thing you write in an LLM application. Define role, constraints, and output format explicitly. Use few-shot examples for structured output tasks — 3-5 examples beat any amount of instruction text. Use chain-of-thought for reasoning tasks. Set temperature deliberately — low for deterministic, high for creative. Version prompt templates like code — a prompt change is a behavior change. Exhaust prompting before reaching for fine-tuning. Treat user input in prompts as untrusted. → `engineering-knowledge-repository/prompt-engineering.md`

## Related Entries
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — RAG injects retrieved context into prompts
- [LLM Evaluation](llm-evaluation.md) — prompts must be evaluated systematically, not just eyeballed
- [LLM Guardrails](llm-guardrails.md) — prompt design is the first layer of output safety
- [Context Window Management](context-window-management.md) — prompts consume context; managing window size is part of prompt design
- [Few-Shot Learning](few-shot-learning.md) — few-shot prompting is the in-context learning form of few-shot learning
- [Agent Patterns](agent-patterns.md) — agent orchestration relies heavily on system prompts and CoT
- [Structured-Prompt-Driven Development](structured-prompt-driven-development.md) — SPDD elevates prompt engineering from craft into a governed delivery methodology; prompts become versioned, reviewed artifacts
- [REASONS Canvas](reasons-canvas.md) — a seven-part structured prompt template that formalizes system prompt design for code generation contexts

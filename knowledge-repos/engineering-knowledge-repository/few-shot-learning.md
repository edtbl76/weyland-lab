---
id: few-shot-learning
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [transfer-learning, prompt-engineering, fine-tuning, data-augmentation]
complexity: intermediate
---

# Few-Shot Learning

## What It Is
The ability of a model to generalize to new tasks from a very small number of labeled examples — typically 1 to 20. Few-shot learning matters because labeled data is expensive, and many real-world ML tasks have insufficient labeled examples for traditional training. Modern LLMs exhibit strong few-shot learning through in-context learning (examples in the prompt) — distinct from traditional few-shot learning approaches that require meta-learning or specialized architectures.

## When to Apply
- New classification or extraction tasks with limited labeled data
- Rapid prototyping to validate that a task is solvable before investing in data collection
- Cases where full fine-tuning is impractical due to data scarcity

## Key Concepts
- **Zero-Shot**: No examples provided. The model uses only its pretrained knowledge and the task description. Lowest data requirement; highest variance
- **One-Shot**: One example provided. The model generalizes from a single demonstration
- **Few-Shot (in-context)**: 2-20 examples provided in the prompt. The model learns the task pattern from the examples without weight updates. This is the LLM-native approach — examples are part of the prompt
- **Meta-Learning**: Traditional few-shot learning approach — trains a model to learn quickly from few examples by training on many diverse tasks. MAML (Model-Agnostic Meta-Learning) is the foundational algorithm. More relevant for non-LLM models
- **Example Selection**: Few-shot performance is sensitive to which examples are chosen. Best practices: examples should be diverse (cover different cases), correctly labeled, and similar to the test distribution. Retrieval-based example selection (find the most similar examples to the query) outperforms fixed examples
- **Format Consistency**: Few-shot examples must use exactly the same format as the expected output. Inconsistent formatting in examples degrades performance significantly
- **Prompt Sensitivity**: LLM few-shot learning is sensitive to example order, phrasing, and format. Evaluate with multiple example orderings; use the most stable configuration
- **Chain-of-Thought Few-Shot**: Include reasoning steps in few-shot examples: `"Input: X → Reasoning: [step-by-step] → Output: Y"`. Dramatically improves performance on reasoning tasks compared to input-output-only examples
- **Prototypical Networks**: A metric-learning approach for traditional few-shot learning — compute class prototypes from support examples; classify by nearest prototype distance. Effective for image classification with few examples

## In Practice
Method uses few-shot prompting for new LLM tasks during prototyping — 3-5 examples in the system prompt validate feasibility before committing to data collection. Example selection uses semantic similarity (retrieve the most similar examples to the current query from a curated pool). Chain-of-thought few-shot is used for extraction and classification tasks requiring reasoning.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Few-Shot Learning**: For LLMs, few-shot = examples in the prompt. Include 3-5 high-quality, diverse examples before asking the model to perform a task. Use chain-of-thought examples for reasoning tasks — include the reasoning steps, not just input/output. Select examples dynamically: retrieve the most semantically similar examples to the current query from a curated pool rather than using fixed examples. Be consistent in format — the model learns the pattern from the examples. Validate zero-shot and few-shot before investing in fine-tuning data collection. → `engineering-knowledge-repository/few-shot-learning.md`

## Related Entries
- [Transfer Learning](transfer-learning.md) — few-shot learning leverages pretrained representations
- [Prompt Engineering](prompt-engineering.md) — few-shot prompting is the in-context learning form of few-shot learning
- [Fine-Tuning](fine-tuning.md) — fine-tuning is the alternative when few-shot performance is insufficient
- [Data Augmentation](data-augmentation.md) — augmentation expands limited labeled datasets to support better few-shot baselines

---
id: fine-tuning
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, nfr-requirements]
related: [transfer-learning, fine-tuning-vs-rag, experiment-tracking, hyperparameter-tuning, model-registry, data-versioning]
complexity: intermediate
---

# Fine-Tuning

## What It Is
The process of continuing the training of a pretrained model on a task-specific dataset to adapt it for a specific use case. Fine-tuning updates the model's weights to specialize its behavior — teaching it a particular style, format, domain vocabulary, or task pattern. For LLMs, fine-tuning is used to adapt general-purpose models to follow specific instructions, adopt a tone, or perform domain-specific tasks consistently.

## When to Apply
- When prompt engineering and RAG cannot achieve the required behavior — fine-tuning is the next step
- Teaching the model a consistent output format or style that prompting alone doesn't reliably produce
- Domain specialization with stable knowledge and sufficient training data (> 1,000 high-quality examples)
- Latency-sensitive inference where a smaller fine-tuned model can match a larger prompted model

## When Not to Apply
- When RAG can solve the problem — fine-tuning is more expensive and slower to update
- When training data is insufficient (< 100 examples for most tasks)
- When the task requires knowledge that changes frequently — fine-tuned knowledge is baked in and expensive to update

## Key Concepts
- **Full Fine-Tuning**: Update all model weights on the task dataset. Highest quality ceiling; most expensive compute; risk of catastrophic forgetting
- **LoRA (Low-Rank Adaptation)**: Add small rank-decomposition matrices alongside frozen pretrained weights. Train only the LoRA parameters (~0.1% of total weights). Near-full-fine-tuning quality at a fraction of the compute. The standard for LLM fine-tuning
- **QLoRA**: LoRA applied to a quantized (4-bit) base model. Enables fine-tuning large models (70B+) on consumer GPUs. Trades some quality for dramatic compute reduction
- **Supervised Fine-Tuning (SFT)**: Training on input/output pairs — the standard approach. Dataset format: `{"prompt": "...", "completion": "..."}`
- **RLHF (Reinforcement Learning from Human Feedback)**: Fine-tuning using human preference data — a reward model learns human preferences; the LLM is trained to maximize reward. Used by OpenAI and Anthropic for instruction following. Complex; not typically done outside of foundation model providers
- **DPO (Direct Preference Optimization)**: A simpler alternative to RLHF for preference-based fine-tuning — directly optimizes on human preference pairs without a separate reward model
- **Training Data Quality**: For fine-tuning, 1,000 high-quality examples outperform 100,000 mediocre ones. Data quality is more important than quantity. Curate carefully
- **Evaluation Before and After**: Establish baseline performance on an evaluation set before fine-tuning. Measure improvement. Ensure fine-tuning improves the target task without degrading general capability
- **Overfitting**: Fine-tuning on too few examples or too many epochs overfits — the model memorizes training data rather than generalizing. Monitor validation loss; use early stopping
- **Frameworks**: HuggingFace `transformers` + `trl` (SFT, DPO), Axolotl, LlamaFactory — standard fine-tuning toolchains. OpenAI Fine-Tuning API for managed fine-tuning of OpenAI models

## In Practice
Method LLM fine-tuning uses LoRA via the HuggingFace `trl` library. Training data is curated to 1,000-5,000 high-quality examples. Experiments are tracked in MLflow. Evaluation runs on a held-out golden set before and after. Fine-tuned models are registered in the model registry with full training provenance. OpenAI's fine-tuning API is used for GPT models when infrastructure management is not desired.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Fine-Tuning**: Use LoRA — it achieves near-full-fine-tuning quality at a fraction of the compute cost by training only a tiny fraction of parameters. Data quality beats data quantity — 1,000 excellent examples beat 100,000 mediocre ones. Always evaluate on a held-out set before and after — confirm improvement on the target task and check for capability regression. Version your training data (DVC) and log your experiments (MLflow). Fine-tuned models must go through the model registry before production. Exhaust prompt engineering and RAG before fine-tuning. → `engineering-knowledge-repository/fine-tuning.md`

## Related Entries
- [Transfer Learning](transfer-learning.md) — fine-tuning is the most common form of transfer learning
- [Fine-Tuning vs. RAG](fine-tuning-vs-rag.md) — decision framework for when fine-tuning is the right choice
- [Experiment Tracking](experiment-tracking.md) — fine-tuning experiments require systematic tracking
- [Hyperparameter Tuning](hyperparameter-tuning.md) — learning rate, epochs, LoRA rank are critical fine-tuning hyperparameters
- [Model Registry](model-registry.md) — fine-tuned models are registered before deployment
- [Data Versioning](data-versioning.md) — fine-tuning datasets must be versioned for reproducibility

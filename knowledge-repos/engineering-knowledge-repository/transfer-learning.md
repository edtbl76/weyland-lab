---
id: transfer-learning
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, requirements-analysis]
related: [fine-tuning, fine-tuning-vs-rag, few-shot-learning, experiment-tracking]
complexity: intermediate
---

# Transfer Learning

## What It Is
A machine learning technique where a model trained on one task or dataset is reused as the starting point for a model on a different (but related) task or dataset. Rather than training from scratch, transfer learning leverages representations learned from large-scale pretraining — general patterns in language, vision, or other domains — and adapts them to a specific downstream task with far less data and compute. The foundation of modern deep learning: BERT, GPT, ResNet, and similar pretrained models are transferred and adapted rather than trained from scratch.

## When to Apply
- Any deep learning task where labeled data is limited — transfer learning compensates for small datasets
- NLP tasks (classification, NER, summarization) — always start from a pretrained language model
- Computer vision tasks — always start from a pretrained vision model (ImageNet-pretrained ResNet, ViT)
- When training from scratch is computationally prohibitive

## When Not to Apply
- Tasks with abundant labeled data where a specialized architecture from scratch may outperform pretrained models
- When the source domain is too dissimilar from the target domain — negative transfer can hurt performance

## Key Concepts
- **Pretrained Model**: A model trained on a large, general dataset — language (Common Crawl, The Pile), images (ImageNet, LAION), code (GitHub). The model learns general representations applicable to many downstream tasks
- **Fine-Tuning**: Continuing training the pretrained model on task-specific data, updating (some or all) weights. The most common transfer learning approach. See Fine-Tuning entry
- **Feature Extraction**: Freeze pretrained weights; use the model as a fixed feature extractor; train only a classification head on top. Faster and cheaper than fine-tuning; lower ceiling
- **Domain Adaptation**: Adapting a model to a target domain through continued pretraining on domain-specific unlabeled data before fine-tuning — bridges the gap between general pretraining and specialized domains (medical, legal, code)
- **Zero-Shot Transfer**: Applying a pretrained model to a task without any task-specific training. GPT-4 answering legal questions without legal fine-tuning is zero-shot transfer. Enabled by large-scale pretraining
- **Catastrophic Forgetting**: Fine-tuning on a narrow task can cause the model to lose general capabilities. Mitigation: use lower learning rates, train for fewer epochs, or use parameter-efficient fine-tuning (LoRA)
- **Parameter-Efficient Fine-Tuning (PEFT)**: Techniques that update only a small fraction of model parameters — LoRA (Low-Rank Adaptation), prefix tuning, adapters. Reduces compute and storage cost while preserving general capabilities
- **Hugging Face Transformers**: The standard library for loading and fine-tuning pretrained models — `AutoModel.from_pretrained()` is the entry point for transfer learning in NLP

## In Practice
Method ML systems default to pretrained models from Hugging Face for NLP tasks. Feature extraction (frozen backbone + trained head) is used for low-data scenarios. Fine-tuning is applied when feature extraction performance is insufficient and training data is available. LoRA is used for LLM fine-tuning to manage compute cost.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Transfer Learning**: Never train a deep learning model from scratch when a pretrained model exists for your domain. Start from a pretrained model, add your task-specific head, fine-tune on your data. Feature extraction (frozen backbone) is faster and cheaper — try it first before full fine-tuning. For LLMs, use LoRA for parameter-efficient fine-tuning rather than updating all weights. Hugging Face Model Hub has pretrained models for almost every domain and modality. Domain adaptation (continue pretraining on domain text before fine-tuning) improves performance for specialized domains. → `engineering-knowledge-repository/transfer-learning.md`

## Related Entries
- [Fine-Tuning](fine-tuning.md) — the most common application of transfer learning
- [Fine-Tuning vs. RAG](fine-tuning-vs-rag.md) — transfer learning (fine-tuning) vs. retrieval as knowledge adaptation strategies
- [Few-Shot Learning](few-shot-learning.md) — transfer learning enables few-shot generalization from minimal examples
- [Experiment Tracking](experiment-tracking.md) — transfer learning experiments require tracking pretrained model version, training data, and hyperparameters

---
id: inference-optimization
tags: [ai-ml, performance, backend]
surfaces-at: [application-design, functional-design]
related: [model-serving, llm-cost-optimization, online-vs-batch-inference, llm-caching, fine-tuning]
complexity: advanced
---

# Inference Optimization

## What It Is
The set of techniques for reducing the computational cost, latency, and memory footprint of running machine learning models in production — particularly large language models and deep neural networks. Training a model is a one-time cost; inference is the cost paid on every prediction request. As models scale (GPT-4 class LLMs requiring hundreds of billions of parameters), inference cost dominates the operational budget. Inference optimization techniques reduce this cost through compression (smaller models), hardware efficiency (better GPU utilization), and architectural tricks (batching, caching) — often with minimal impact on output quality.

## When to Apply
- LLM or deep learning model serving with latency SLOs that cannot be met with vanilla deployment
- When inference cost is a significant fraction of the service's operational budget
- Before scaling model serving infrastructure — optimize the model before scaling the fleet
- When deploying models to resource-constrained environments (edge devices, mobile, low-memory containers)
- Before fine-tuning: optimizing a smaller base model often produces better cost/performance than fine-tuning a large one

## Key Concepts
- **Quantization**: Reducing the numerical precision of model weights from 32-bit floats (FP32) to lower precision (FP16, INT8, INT4). FP16 roughly halves memory and speeds up inference on modern GPUs. INT8 (8-bit integer quantization) reduces further with small accuracy loss. Tools: `bitsandbytes`, `GPTQ`, `AWQ` for LLMs; `TensorRT` for neural networks. Post-training quantization requires no retraining; quantization-aware training produces better results
- **Distillation**: Training a smaller "student" model to mimic the outputs of a larger "teacher" model. The student learns from the teacher's probability distributions (soft labels), not just the ground truth, and achieves comparable performance at a fraction of the size. Example: DistilBERT is 40% smaller than BERT with 97% of BERT's performance. Best for: replacing large models in specific task domains
- **Pruning**: Removing redundant weights (those close to zero) from the model. Structured pruning removes entire attention heads or layers (faster inference); unstructured pruning removes individual weights (requires sparse matrix support). Less common in practice than quantization for LLMs
- **Batching**: Processing multiple inference requests together in a single forward pass. GPU utilization increases dramatically with batch size; latency per request decreases. For LLM serving, dynamic batching (grouping requests that arrive close together) and continuous batching (interleaving requests in-flight) are key optimizations. Tools: vLLM, TGI (Text Generation Inference), TensorRT-LLM
- **KV Cache**: For autoregressive LLMs, the key-value attention cache allows reusing computations across tokens in a sequence. Efficient KV cache management (PagedAttention in vLLM) dramatically improves throughput for long sequences
- **Speculative Decoding**: A small "draft" model generates candidate tokens quickly; the larger model verifies them in parallel. Achieves 2-4x speedup on LLM generation with identical output quality
- **Model Parallelism**: For models too large for a single GPU, split the model across GPUs (tensor parallelism: split layers; pipeline parallelism: split layers sequentially). Required for 70B+ parameter models
- **Hardware Selection**: H100 > A100 > A10G for LLM inference. Inferentia2 (AWS) and TPUs (Google) offer cost-efficient inference for production. CPU inference (via ONNX Runtime, llama.cpp) is viable for small models or batch workloads where latency requirements are relaxed

## In Practice
Method AI services use vLLM for LLM inference serving with continuous batching and PagedAttention. INT4 quantization (AWQ) is applied to open-source models (Llama 3, Mistral) to fit larger models on fewer GPUs without meaningful quality degradation. Smaller task-specific models (classification, extraction) use ONNX Runtime with INT8 quantization. Inference SLOs drive hardware selection: P95 latency < 2s → A10G; < 500ms → A100 or H100.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Inference Optimization**: The cost of LLM inference compounds with every request; optimization before scaling is far cheaper than scaling unoptimized models. INT4/INT8 quantization is the highest-ROI technique — it halves memory usage with minimal quality loss and requires no retraining. For throughput-optimized serving, vLLM's continuous batching dramatically outperforms naive request-at-a-time serving. Benchmark your specific workload: theoretical GPU benchmarks don't reflect real prompt/response length distributions. Optimize for the right metric — cost per token for batch workloads; P95 latency for interactive applications. → `engineering-knowledge-repository/inference-optimization.md`

## Related Entries
- [Model Serving](model-serving.md) — inference optimization techniques are applied to the model serving layer
- [LLM Cost Optimization](llm-cost-optimization.md) — inference optimization is the primary lever for reducing LLM operational costs
- [Online vs. Batch Inference](online-vs-batch-inference.md) — different serving modes have different optimization targets (latency vs. throughput)
- [LLM Caching](llm-caching.md) — semantic and prompt caching complement inference optimization to reduce compute entirely for repeated requests
- [Fine-Tuning](fine-tuning.md) — fine-tuning smaller models often produces better cost/quality than serving large general models

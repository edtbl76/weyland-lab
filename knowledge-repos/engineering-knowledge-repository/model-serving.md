---
id: model-serving
tags: [pattern, ai-ml, backend, infrastructure, cloud]
surfaces-at: [application-design, infrastructure-design, nfr-requirements]
related: [online-vs-batch-inference, model-registry, auto-scaling, mlops, llm-cost-optimization]
complexity: intermediate
---

# Model Serving

## What It Is
The infrastructure and patterns for deploying trained ML models to serve predictions to applications in production. Model serving covers: how models are packaged, how prediction endpoints are exposed, how latency and throughput SLOs are met, how models are versioned and updated, and how infrastructure scales with demand. The right serving architecture depends on whether predictions are needed in real time or in batch.

## When to Apply
- Every production ML deployment — the serving layer is how applications consume model predictions
- When designing NFRs: latency targets, throughput requirements, and cost budgets drive serving architecture decisions

## Key Concepts
- **REST Inference Endpoint**: The most common pattern — wrap the model in an HTTP service that accepts prediction requests and returns responses. FastAPI + Uvicorn for Python; TorchServe, TensorFlow Serving for framework-native serving
- **Model Packaging**: Standardized formats for portable, reproducible model artifacts — ONNX (cross-framework, hardware-optimized), MLflow Model (format-agnostic, includes dependencies), Hugging Face model format (transformers ecosystem)
- **Batching at Inference**: Grouping multiple prediction requests into a single forward pass — improves GPU utilization and throughput. Dynamic batching (accumulate requests within a time window) vs. static batching (fixed batch size)
- **GPU vs. CPU Serving**: GPU serving provides 10-100x throughput for deep learning models but costs more. CPU serving is sufficient for traditional ML (decision trees, linear models) and small NLP models. LLMs always require GPU or dedicated accelerators
- **Model Server Frameworks**: TorchServe (PyTorch), TensorFlow Serving (TF), Triton Inference Server (NVIDIA, multi-framework) — purpose-built servers with batching, multi-model serving, and GPU optimization
- **BentoML**: Framework for packaging and deploying ML models as APIs — supports multiple frameworks, cloud deployment, and monitoring integration
- **KServe / Seldon**: Kubernetes-native model serving platforms — standardized serving infrastructure, canary deployments, explainability, A/B testing. Used in large-scale ML platform deployments
- **Latency SLOs**: Set explicit P50, P95, and P99 latency targets. LLM serving has inherently higher latency (time to first token, tokens per second). Traditional ML should target P99 < 100ms
- **Multi-Model Serving**: Serving multiple models from a single server — saves infrastructure cost for many low-traffic models
- **Feature Preprocessing at Serving**: Lightweight feature transformations at serving time must match training transformations exactly — a common source of training-serving skew

## In Practice
Method ML serving uses FastAPI for simple Python models, TorchServe for PyTorch deep learning models, and vLLM for LLM serving. Kubernetes with KServe handles canary deployments and traffic splitting. GPU node pools are provisioned for deep learning and LLM inference. All serving endpoints have P99 latency SLOs and auto-scale based on request queue depth.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Model Serving**: Wrap models in a REST API; don't call Python scripts directly from application code. Package with ONNX or MLflow for portability. Use dynamic batching for GPU models — it multiplies throughput. Set P99 latency SLOs before deployment; measure against them continuously. LLMs require GPU and specialized servers (vLLM, TGI) — vanilla FastAPI is too slow. Use KServe or Seldon for Kubernetes-native multi-model serving with built-in canary. Pull the serving artifact from the model registry — never deploy from a notebook. → `engineering-knowledge-repository/model-serving.md`

## Related Entries
- [Online vs. Batch Inference](online-vs-batch-inference.md) — serving architecture varies significantly by inference mode
- [Model Registry](model-registry.md) — serving infrastructure pulls versioned model artifacts from the registry
- [Auto-Scaling](auto-scaling.md) — model serving endpoints must auto-scale with prediction request volume
- [MLOps](mlops.md) — model serving is the production delivery component of MLOps
- [LLM Cost Optimization](llm-cost-optimization.md) — self-hosted model serving trades API cost for infrastructure cost

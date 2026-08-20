---
id: online-vs-batch-inference
tags: [pattern, ai-ml, backend, performance]
surfaces-at: [application-design, nfr-requirements]
related: [model-serving, asynchronous-processing, mlops, llm-cost-optimization, feature-stores]
complexity: foundational
---

# Online vs. Batch Inference

## What It Is
Two fundamental modes for serving ML model predictions: online inference (real-time, synchronous, per-request) and batch inference (asynchronous, scheduled, bulk). Most ML systems use both — the choice per use case depends on whether the user needs a prediction immediately or whether predictions can be pre-computed and looked up.

## When to Apply
- Online inference: user-facing features requiring immediate predictions (recommendations at page load, real-time fraud scoring, live search ranking)
- Batch inference: predictions that can be computed ahead of time and stored (daily email recommendations, nightly risk scores, document classification pipelines)

## Key Concepts

**Online Inference**:
- Prediction requested at inference time; result returned in the response
- Latency-sensitive — P99 must meet user-facing SLO (typically < 200ms for web, < 50ms for search)
- Requires always-on serving infrastructure
- Uses the latest model and features — predictions reflect current state
- Harder to scale for burst traffic without autoscaling infrastructure
- Cost scales with request volume

**Batch Inference**:
- Model runs on a large dataset on a schedule; predictions stored in a database or cache
- No latency requirement during inference — can run for hours
- Much cheaper per prediction — GPU utilization is high, no idle capacity
- Predictions may be stale (computed at batch time, not request time)
- Simple architecture — just a scheduled job writing to a table
- LLM batch APIs (OpenAI Batch, Anthropic Batch) offer 50% cost reduction for async processing

**Hybrid Pattern — Precomputed + Fallback**:
- Pre-compute predictions for the most common cases (top 1M users); serve in real-time from cache
- Fall back to online inference for the long tail (users not in the precomputed set)
- Combines low latency (cache hit) with coverage (online fallback)

**Near-Real-Time Inference**:
- A middle ground — predictions computed with a short lag (seconds to minutes) using streaming pipelines
- Fresher than daily batch; cheaper than per-request online serving
- Used for fraud scoring on completed transactions, feed ranking with sub-minute freshness

**Decision Framework**:
| | Online | Batch | Near-Real-Time |
|---|---|---|---|
| Latency | Milliseconds | N/A (precomputed) | Seconds-minutes |
| Freshness | Real-time | Stale (hours-days) | Near-fresh |
| Cost | High | Low | Medium |
| Use case | Interactive features | Bulk scoring | Streaming features |

## In Practice
Method ML systems default to batch inference where latency allows — it's simpler and cheaper. Online inference is added when the feature requires real-time predictions. Precomputed + fallback is used for recommendation systems where the top cohort can be precomputed but tail coverage requires online serving. LLM workloads use the batch API for non-user-facing processing.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Online vs. Batch Inference**: Default to batch — simpler, cheaper, easier to debug. Add online inference only when the feature requires real-time predictions. Use precomputed + fallback for recommendation and personalization: pre-score the top N users nightly, serve from cache, online for the rest. LLM batch APIs (OpenAI Batch, Anthropic Batch) cost 50% less for async processing — use them for document analysis and classification pipelines. Near-real-time inference (streaming) fills the gap between batch staleness and online cost. → `engineering-knowledge-repository/online-vs-batch-inference.md`

## Related Entries
- [Model Serving](model-serving.md) — the serving infrastructure for online inference
- [Asynchronous Processing](asynchronous-processing.md) — batch inference is a batch asynchronous processing pattern
- [MLOps](mlops.md) — inference mode is an MLOps architecture decision
- [LLM Cost Optimization](llm-cost-optimization.md) — batch LLM inference APIs reduce cost significantly
- [Feature Stores](feature-stores.md) — online stores serve features for online inference; offline stores for batch

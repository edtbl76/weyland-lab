---
id: model-routing
tags: [pattern, ai-ml, backend, infrastructure]
surfaces-at: [application-design, infrastructure-design, nfr-design]
related: [model-serving, model-abstraction-layer, circuit-breaker, api-gateway-pattern, llm-cost-optimization, model-monitoring]
complexity: intermediate
---

# Model Routing

## What It Is
A runtime pattern for dynamically directing AI inference requests to different models or providers based on task characteristics, cost targets, latency requirements, or provider health. Rather than statically binding an application to a single model, model routing evaluates each request against a set of rules or a classification policy and selects the most appropriate model from a pool. This enables a single application to use fast, inexpensive models for simple tasks and more capable (but slower, costlier) models for complex tasks — simultaneously reducing cost and improving response quality where it matters. Model routing typically lives inside or alongside a Model Abstraction Layer, which provides the provider-agnostic interface through which routing dispatches calls.

## When to Apply
- Applications with heterogeneous task types where a single model is either over-powered (expensive) for simple tasks or under-powered for complex ones
- Multi-provider architectures where fallback to a secondary provider is needed for resilience
- High-volume AI workloads where cost optimization is an active NFR — routing to cheaper models for eligible requests reduces cost without sacrificing quality
- Regulated environments where certain task types must be routed to specific models for compliance reasons (e.g., on-premises or sovereign cloud deployment)

## When Not to Apply
- Single-model, low-volume applications where routing complexity outweighs the benefit
- Applications where routing decisions would require full document analysis — the routing overhead exceeds the benefit

## Key Concepts
- **Task Complexity Classification**: The routing layer classifies incoming requests by complexity before dispatching. Classification signals: token count, request type, presence of code, domain keywords, user tier. Route simple/short requests to fast, inexpensive models; complex/long requests to capable models
- **Provider Failover**: When a primary provider is unavailable or degraded, the router automatically falls back to a secondary provider. This is a circuit breaker applied at the model provider level — see Circuit Breaker entry. Failover requires the Model Abstraction Layer to normalize provider-specific responses so the application receives a consistent schema regardless of which provider answered
- **Cost-Based Routing**: Track per-request cost in real time. When approaching budget thresholds, the router can downgrade to a cheaper model tier for non-critical requests while preserving the capable model for high-priority traffic
- **Latency-Based Routing**: Route time-sensitive requests to faster models and batch or background requests to slower, more capable models. Set P99 latency thresholds per request class; the router selects within constraint
- **Routing Rules vs. Routing Policies**: Rules are explicit conditions ("if request contains code, use model X"). Policies are learned or probabilistic ("use model X for 80% of type-A requests"). Start with rules; graduate to policies when rules proliferate
- **Semantic Routing**: Use a lightweight classifier or embedding-based similarity to route requests to task-specialized models (coding model, summarization model, reasoning model). The classifier runs fast and cheap; the specialized model handles the heavy lifting
- **Model Versioning in Routing**: The routing layer resolves model IDs from the model registry, not from hardcoded strings. When a new model version is deployed, routing is updated via configuration — not code changes. See Model Registry entry
- **Observability**: Every routing decision must be logged — which model was selected, why (rule triggered), latency, cost, and outcome. This telemetry is the input for routing rule tuning

## In Practice
Method routing implementations use a rules-based router as the starting point: classify requests by token count and type, route to smaller/cheaper models for short/simple requests and to larger models for complex requests. Provider failover is implemented using the circuit breaker pattern with a 30-second open state and exponential backoff on retry. All routing decisions are logged to the LLM observability platform with cost and latency per decision. Cost-based routing is triggered when daily spend crosses 80% of budget — eligible requests are downgraded automatically.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Model Routing**: One model for all tasks is almost always wrong — it is either too slow and expensive for simple work or too weak for complex work. Route by task complexity: use a fast, cheap model for classification and triage; use a capable model for reasoning and synthesis. Build fallback chains across providers — model APIs have outages; treat them like any other external dependency with circuit breakers and failover. Log every routing decision with cost and latency so you can tune rules with data. Never hardcode model IDs in routing logic — resolve from a registry or configuration so you can update routing without a deployment. → `engineering-knowledge-repository/model-routing.md`

## Related Entries
- [Model Serving](model-serving.md) — model routing dispatches to serving endpoints; serving handles the actual inference execution
- [Model Abstraction Layer](model-abstraction-layer.md) — routing logic lives inside the abstraction layer, which provides the provider-agnostic interface
- [Circuit Breaker](circuit-breaker.md) — provider failover in model routing implements the circuit breaker pattern
- [API Gateway Pattern](api-gateway-pattern.md) — model routing can be implemented as an AI-specific API gateway in front of multiple model endpoints
- [LLM Cost Optimization](llm-cost-optimization.md) — cost-based routing is one of the primary levers for LLM cost optimization at runtime
- [Model Monitoring](model-monitoring.md) — routing telemetry feeds model monitoring; quality degradation on routed providers is surfaced in monitoring

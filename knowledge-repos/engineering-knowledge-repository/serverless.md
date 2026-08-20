---
id: serverless
tags: [pattern, cloud, backend]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [event-driven-architecture, twelve-factor-app, microservices, api-gateway-pattern]
complexity: intermediate
---

# Serverless

## What It Is
A cloud execution model where the cloud provider manages the server infrastructure entirely. Code runs in stateless, ephemeral functions (FaaS — Function as a Service) that are invoked by events, scale automatically from zero, and are billed by execution time rather than reserved capacity. "Serverless" doesn't mean no servers — it means you don't manage them. Common platforms: AWS Lambda, Azure Functions, Google Cloud Functions.

## When to Apply
- Event-driven workloads with irregular or unpredictable traffic patterns
- Background processing tasks (image processing, notifications, data transformation)
- APIs with low-to-moderate, variable traffic where scale-to-zero economics are attractive
- Rapid prototyping and MVPs where operational simplicity is valued
- Workflows and automation tasks with infrequent execution

## When Not to Apply
- Long-running processes — most FaaS platforms have execution time limits (15 min for Lambda)
- High-throughput, consistently high-load services where reserved capacity is more economical
- Workloads sensitive to cold-start latency (first invocation after idle period has higher latency)
- Teams without cloud expertise — serverless shifts complexity to cloud configuration and IAM
- Stateful workloads that require persistent in-memory state

## Key Concepts
- **Function as a Service (FaaS)**: The unit of deployment is a function, not a service or container
- **Event Trigger**: Functions are invoked by events — HTTP requests, queue messages, scheduled triggers, database changes, file uploads
- **Stateless**: Functions have no persistent state — state lives in external stores (databases, caches, S3)
- **Scale to Zero**: No traffic = no cost. Scales up automatically on demand, back to zero when idle.
- **Cold Start**: The latency penalty when a function is invoked after being idle — the container must be initialized
- **Managed Infrastructure**: The platform handles OS patching, scaling, availability — you manage only the function code and configuration

## In Practice
Serverless is a natural fit for event-driven architectures — Lambda functions triggered by SQS/SNS messages, S3 events, or API Gateway requests are a common pattern in Method engagements. The twelve-factor principles (stateless processes, config in environment) are prerequisites for serverless. In Infrastructure Design, the decision between serverless and containerized compute depends on traffic patterns, latency requirements, and cost modeling.

## Engineering Knowledge
💡 **Engineering Knowledge — Serverless**: For event-driven or variable-traffic workloads, serverless eliminates server management and delivers automatic scaling with pay-per-execution economics. The tradeoffs are real: cold starts, execution time limits, and shifted complexity to cloud config. Model your traffic pattern — serverless saves money and ops overhead when traffic is spiky; reserved compute wins for consistently high load. → `engineering-knowledge-repository/architectural-styles/serverless.md`

## Related Entries
- [Event-Driven Architecture](event-driven-architecture.md) — serverless functions are natural event consumers
- [Twelve-Factor App](../architectural-philosophy/twelve-factor-app.md) — twelve-factor principles are prerequisites for serverless
- [API Gateway Pattern](api-gateway-pattern.md) — the standard HTTP trigger for serverless APIs

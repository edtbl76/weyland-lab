---
id: auto-scaling
tags: [pattern, infrastructure, cloud, performance]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [horizontal-vs-vertical-scaling, cloud-native-design, container-orchestration, serverless]
complexity: intermediate
---

# Auto-Scaling

## What It Is
The automatic adjustment of compute capacity in response to real-time demand signals. Auto-scaling adds instances when load increases and removes them when load decreases — maintaining performance without over-provisioning. It operates at multiple levels: cloud VMs (AWS Auto Scaling Groups), containers (Kubernetes Horizontal Pod Autoscaler), and serverless functions (scale to zero on idle).

## When to Apply
- Any service with variable or unpredictable traffic patterns
- Cost optimization — auto-scaling eliminates the need to provision for peak capacity at all times
- Production services with SLO requirements — auto-scaling prevents performance degradation under load spikes
- Services that need to scale to zero (serverless) for cost efficiency during idle periods

## When Not to Apply
- Databases and stateful services — auto-scaling doesn't apply to stateful services in the same way; use read replicas and vertical scaling instead
- Services with very fast traffic spikes where scale-out latency matters — pre-warm capacity or use serverless instead
- Services with bursty short-duration load — scale-out takes 1-3 minutes; if traffic spikes last 30 seconds, auto-scaling may not react in time

## Key Concepts
- **Horizontal Pod Autoscaler (HPA)**: Kubernetes controller that scales Pod replicas based on CPU, memory, or custom metrics
- **Vertical Pod Autoscaler (VPA)**: Adjusts container resource requests/limits — scales up vs. scale out
- **KEDA (Kubernetes Event-Driven Autoscaling)**: Scales based on external metrics — queue depth, SQS message count, custom events
- **AWS Auto Scaling Group (ASG)**: Manages EC2 instance count based on CloudWatch metrics
- **Cooldown Period**: Prevents scale-in too aggressively after a spike — allows the system to stabilize before removing instances
- **Target Tracking**: Scale to maintain a target metric value (e.g., maintain 60% average CPU) rather than threshold-based rules
- **Scale-In Protection**: Prevent in-flight requests from being killed during scale-in — drain connections before terminating instances

## In Practice
Kubernetes HPA is the standard auto-scaling mechanism for container workloads in Method engagements. Configure scaling based on custom metrics (RPS, queue depth) rather than CPU alone — CPU is a lagging indicator. KEDA is the preferred solution for event-driven scaling (scale to zero on empty queue). Configure scale-in protection to avoid dropping in-flight requests.

## Engineering Knowledge
💡 **Engineering Knowledge — Auto-Scaling**: Configure auto-scaling so the system provisions capacity automatically when needed and releases it when idle. HPA in Kubernetes scales Pods based on CPU, memory, or custom metrics (RPS via KEDA is better than CPU for most web services — CPU is a lagging indicator). Configure scale-in protection to avoid dropping in-flight requests during scale-in. For queued workloads, scale based on queue depth (KEDA) — scale to zero on empty, scale up fast on messages. → `engineering-knowledge-repository/cloud-patterns/auto-scaling.md`

## Related Entries
- [Horizontal vs. Vertical Scaling](../performance/horizontal-vs-vertical-scaling.md) — auto-scaling automates horizontal scaling
- [Container Orchestration](container-orchestration.md) — Kubernetes provides the auto-scaling infrastructure
- [Serverless](../architectural-styles/serverless.md) — serverless is auto-scaling taken to its logical extreme (including scale-to-zero)

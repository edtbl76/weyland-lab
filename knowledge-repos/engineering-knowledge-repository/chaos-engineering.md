---
id: chaos-engineering
tags: [methodology, testing, reliability, distributed-systems]
surfaces-at: [nfr-requirements, nfr-design, infrastructure-design]
related: [circuit-breaker, bulkhead-pattern, retry-pattern, site-reliability-engineering, test-pyramid]
complexity: advanced
---

# Chaos Engineering

## What It Is
The discipline of experimenting on a system in production (or production-equivalent environments) to build confidence in its ability to withstand turbulent conditions. Chaos Engineering deliberately injects failures — network latency, instance termination, dependency failures — to validate that resilience mechanisms actually work before real failures occur. Pioneered by Netflix with Chaos Monkey.

## When to Apply
- Production systems with resilience requirements — verify circuit breakers, retries, and bulkheads actually work
- Before high-traffic events — validate resilience under failure conditions before Black Friday
- After adding new resilience mechanisms — confirm they behave as designed under real conditions
- Mature engineering organizations with strong observability — you can only learn from chaos if you can observe the system's behavior

## When Not to Apply
- Systems without adequate observability — if you can't measure the impact, you can't learn
- Before basic resilience patterns (circuit breakers, retries) are in place — don't create chaos you can't contain
- Production systems where the blast radius of an experiment could be unacceptably large — start in staging
- Teams without incident response capability to handle an experiment that goes wrong

## Key Concepts
- **Steady State**: Define the normal behavior of the system before introducing failure — metrics baselines
- **Hypothesis**: State what you expect to happen when failure is injected (e.g., "when one database replica fails, requests will route to another within 1 second")
- **Blast Radius**: The scope of the failure injection — start small (1 instance, 1% of traffic) and expand as confidence grows
- **Game Day**: A planned chaos experiment event — the team observes and responds together
- **Chaos Monkey**: Netflix's tool that randomly terminates EC2 instances — forces engineers to build resilient services that survive instance loss
- **Fault Injection**: Specific failure modes to inject: latency, packet loss, dependency failures, resource exhaustion, node termination
- **Simian Army**: Netflix's extended toolkit — Chaos Monkey (instance termination), Latency Monkey (network delays), Conformity Monkey (policy violations)

## In Practice
Chaos Engineering is an advanced reliability practice Method recommends for clients with mature SRE capabilities and production-scale systems. Start with scheduled, planned experiments in staging; graduate to production experiments with tight blast radius control. Tools: Chaos Toolkit, AWS Fault Injection Simulator (FIS), Gremlin, LitmusChaos (Kubernetes). The prerequisite is always observability — distributed tracing and real-time metrics are required to learn from experiments.

## Engineering Knowledge
💡 **Engineering Knowledge — Chaos Engineering**: Don't wait for failures to discover your resilience gaps. Deliberately inject failures — terminate instances, add latency, fail dependencies — and observe whether your system degrades gracefully. Start small: 1 instance, staging, planned experiment with the team watching. Define your steady state first; state your hypothesis; measure the outcome. Prerequisites: good observability (you can't learn from chaos you can't see) and existing resilience mechanisms (circuit breakers, retries) to verify. → `engineering-knowledge-repository/testing/chaos-engineering.md`

## Related Entries
- [Circuit Breaker](../infrastructure/circuit-breaker.md) — chaos engineering validates that circuit breakers trip correctly
- [Bulkhead Pattern](../infrastructure/bulkhead-pattern.md) — chaos validates bulkhead isolation under real failure conditions
- [Site Reliability Engineering](../methodologies/site-reliability-engineering.md) — chaos engineering is an advanced SRE practice

---
id: you-build-it-you-run-it
tags: [methodology, team-practices, reliability]
surfaces-at: [application-design]
related: [site-reliability-engineering, on-call-management, incident-management, four-key-metrics, team-topologies]
complexity: foundational
---

# You Build It, You Run It

## What It Is
A DevOps accountability model where the engineering team that builds a service also owns its operational health — including on-call responsibilities, incident response, and production reliability. Popularized by Amazon's CTO Werner Vogels ("you build it, you run it"), this model eliminates the traditional wall between development teams and a separate operations team. When engineers experience the operational consequences of their code — pager alerts, incident response, user-facing errors — they internalize the incentive to make their systems observable, reliable, and operationally simple.

## When to Apply
- Any team shipping services to production with ongoing operational needs
- Organizations transitioning from a centralized operations/NOC model to product team ownership
- Services where the best responders to incidents are the engineers who built the system
- When development velocity is high enough that ops teams cannot maintain context on all services
- As the default model for microservices architectures where each team owns their bounded context

## Key Concepts
- **Operational Ownership**: The team that designs, builds, and deploys a service also defines its SLOs, writes its runbooks, maintains its observability instrumentation, and responds when it pages. There is no handoff to a separate "operations" team
- **On-Call Rotation**: Developers participate in on-call rotations for their own services. This creates direct feedback: overly noisy alerting, missing dashboards, and unclear runbooks become the developer's problem to fix
- **Incentive Alignment**: Teams that run their own services are incentivized to invest in operational quality — reducing alert noise, improving documentation, building self-healing automation. Teams that hand off to ops have no direct feedback loop from production
- **SRE vs. You Build It You Run It**: Site Reliability Engineering (Google model) places SREs as embedded consultants who help product teams achieve reliability targets. "You build it, you run it" places full ownership on the product team. Both models are compatible — SREs can support teams without owning their on-call
- **Platform Team Exception**: Horizontal platform teams (infra, data, ML platform) may have a dedicated SRE function because the breadth of concerns spans many consumer teams. The model still applies — the platform team runs what they build
- **Cognitive Load**: Full operational ownership adds cognitive load. Mitigate with good observability tooling, runbook templates, and SLO frameworks that reduce alert noise. The goal is informed ownership, not operational burden
- **Gradual Transition**: Organizations with centralized ops can transition gradually: first instrument services with observability, then move L2/L3 (complex incidents) ownership to product teams, then L1. Don't transfer ownership without transferring runbooks, dashboards, and context

## In Practice
Method product teams own the services they build, including production on-call. On-call rotations are maintained in PagerDuty. Each service has an SLO documented in the service runbook before launch. Teams review their alert noise weekly — an alert that fires without action for 2 consecutive weeks is deleted or downgraded. Blameless post-mortems after incidents are run by the owning team. Platform and infrastructure services are owned by their respective engineering squads.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — You Build It, You Run It**: Operational ownership creates the incentive loop that drives reliability investment — engineers who get paged at 2am for flaky alerts fix those alerts fast. The model only works if teams have access to good observability tooling, runbook templates, and SLO frameworks; dumping operational burden on teams without infrastructure is how you burn out engineers. The transition from centralized ops should transfer tools and context alongside responsibility. → `engineering-knowledge-repository/you-build-it-you-run-it.md`

## Related Entries
- [Site Reliability Engineering](site-reliability-engineering.md) — SRE is a complementary model; SREs help teams achieve reliability targets without removing team ownership
- [On-Call Management](on-call-management.md) — operational ownership requires sustainable on-call practices to prevent burnout
- [Incident Management](incident-management.md) — owning teams run their own incident response and post-mortems
- [Four Key Metrics](four-key-metrics.md) — DORA metrics measure the outcomes of good operational ownership (MTTR, change failure rate)
- [Team Topologies](team-topologies.md) — team ownership patterns align with stream-aligned team model

---
id: health-dashboards
tags: [tooling, observability]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [golden-signals, metrics-and-alerting, service-level-objectives, synthetic-monitoring, distributed-tracing]
complexity: foundational
---

# Health Dashboards

## What It Is
Visual, real-time displays of system health indicators that give on-call engineers, teams, and stakeholders immediate situational awareness. A good health dashboard answers the question "Is the system healthy right now?" in seconds — without requiring log queries or custom investigations. Dashboards are organized by audience and scope: service-level dashboards for engineers, executive dashboards for SLA stakeholders, infrastructure dashboards for platform teams.

## When to Apply
- All production services — every service needs a health dashboard before going live
- Post-incident — create or improve dashboards from lessons in postmortems
- On-call setup — dashboards are a core on-call tool; build them before putting someone on call

## Key Concepts
- **USE Method (Utilization, Saturation, Errors)**: Brendan Gregg's framework for infrastructure dashboards — for every resource, show utilization, saturation, and error rate
- **RED Method (Rate, Errors, Duration)**: Tom Wilkie's framework for service dashboards — request rate, error rate, request duration. Aligns with Google's Golden Signals
- **Golden Signals Dashboard**: Latency, Traffic, Errors, Saturation panels for a service — the minimum viable service health dashboard
- **Grafana**: The industry standard open-source dashboard platform. Prometheus datasource for metrics; Loki for logs; Tempo for traces. Dashboard as code via JSON model
- **Time Range Selector**: Every dashboard must support flexible time ranges — last 1h, 6h, 24h, 7d. Essential for incident investigation vs. trend analysis
- **Alerting Linkage**: Dashboard panels should link to corresponding alert rules — engineers can see thresholds and current values in the same view
- **SLO Dashboard**: A dedicated dashboard showing SLO compliance, error budget remaining, and burn rate — not just raw metrics
- **Runbook Links**: Annotation links from panels to runbooks — when a panel looks bad, the engineer should know immediately what to do

## In Practice
Method's standard dashboard setup: service health dashboard (RED/Golden Signals), infrastructure dashboard (USE method — CPU, memory, disk, network), SLO dashboard (error budget burn rate). Built in Grafana. Dashboard JSON stored in git alongside service code. Provisioned automatically via Grafana provisioning or the Grafana Terraform provider.

## Engineering Knowledge
💡 **Engineering Knowledge — Health Dashboards**: The first question during an incident is "what's broken?" A good dashboard answers it in 10 seconds. Every production service needs a health dashboard before go-live: RED method (Rate, Errors, Duration) for the service layer; USE method (Utilization, Saturation, Errors) for infrastructure. Store dashboards as code in Git — Grafana supports JSON provisioning. Link panels to runbooks. Add SLO compliance and error budget burn rate. Build the dashboard before you put someone on call. → `engineering-knowledge-repository/observability/health-dashboards.md`

## Related Entries
- [Golden Signals](golden-signals.md) — the four golden signals are the foundation of service health dashboards
- [Metrics and Alerting](metrics-and-alerting.md) — dashboard panels are backed by the same metrics as alerts
- [Service Level Objectives](service-level-objectives.md) — SLO dashboard is a required component of the health dashboard set
- [Synthetic Monitoring](synthetic-monitoring.md) — synthetic probe results appear on health dashboards as availability indicators
- [Distributed Tracing](distributed-tracing.md) — trace data surfaces on dashboards for latency breakdown

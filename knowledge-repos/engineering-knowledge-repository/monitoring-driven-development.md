---
id: monitoring-driven-development
tags: [methodology, observability, developer-experience]
surfaces-at: [application-design, functional-design]
related: [metrics-and-alerting, service-level-objectives, test-driven-development, structured-logging, golden-signals]
complexity: intermediate
---

# Monitoring-Driven Development

## What It Is
A development practice where observability instrumentation — metrics, alerts, dashboards, and SLO definitions — is designed and implemented before or alongside feature code, rather than as an afterthought post-launch. Analogous to test-driven development's "write tests first" discipline, monitoring-driven development (MDD) asks engineers to define "what does healthy look like for this feature?" before writing the implementation. This produces systems where operational visibility is a first-class deliverable, not a retrofit, and where engineers ship features with confidence that failure modes will be detected immediately.

## When to Apply
- New services and features entering production for the first time
- Teams that have experienced "silent failures" — production bugs not detected until users reported them
- Production readiness reviews where observability is a gate
- As part of a production readiness checklist enforcement practice
- Teams adopting SLOs who need to embed SLO thinking into the development workflow

## Key Concepts
- **The Practice**: Before (or concurrently with) writing feature code, define:
  - What metric(s) indicate this feature is working correctly?
  - What alert should fire if the feature fails or degrades?
  - What does the dashboard for this feature look like?
  - What log events should be emitted at key decision points?
  - If this is a user-facing feature: what's the SLO?
- **Failure Mode First Thinking**: MDD requires engineers to enumerate failure modes early: "What are the ways this code could fail silently?" Silent failures (wrong results returned with 200 status, third-party API failing silently, data corruption with no error) are the hardest to catch — they require explicit instrumentation to detect
- **The Monitoring Stub**: A practical technique — add metric emission code (counters, histograms, gauges) before the business logic. `operation_requests_total.inc()` at the entry point; `operation_failures_total.inc()` in error handlers; `operation_duration_seconds.observe()` at completion. The stub ensures the feature is observable from the first line of business logic
- **Dashboard First**: Sketch the operational dashboard for a feature before writing it. What panels exist? "Request rate", "Error rate", "P95 duration", "Queue depth". Designing the dashboard first surfaces what metrics are needed and forces explicit thinking about what "this is working" looks like
- **Alert Design**: Alerts should be designed before go-live: what SLI threshold triggers a page? What's the severity? Who is paged? What's in the runbook? Alerts designed under incident pressure produce noisy, poorly-calibrated alert policies
- **Relationship to SLOs**: MDD operationalizes SLOs at the feature level. An SLO says "99.9% of requests succeed within 200ms"; MDD means the instrumentation, dashboard, and alert that track this SLO are written before the feature ships
- **Test Coverage Analogy**: Just as TDD produces test coverage as a byproduct, MDD produces observability coverage. The discipline is the same: define what "correct" looks like before building, not after

## In Practice
Method's code generation stage includes observability instrumentation as a first-class deliverable. Engineers define metrics and dashboards in the functional design stage. For every new endpoint or significant code path, the implementation includes: a request counter, an error counter, a duration histogram, structured log events at entry and error paths, and a Datadog dashboard panel. SLO definitions are written before go-live.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Monitoring-Driven Development**: The most expensive production bugs are silent failures — systems returning wrong results or losing data with no alerts firing. MDD prevents this by forcing the question "how will I know if this is broken?" before the feature ships. You can't add observability retroactively with the same confidence as when it was designed in. The practice is lightweight: add metric emissions alongside your first passing test, not after the feature is complete. If you can't describe what "healthy" looks like for a feature, that uncertainty should surface in design, not in a 3am incident. → `engineering-knowledge-repository/monitoring-driven-development.md`

## Related Entries
- [Metrics and Alerting](metrics-and-alerting.md) — MDD defines which metrics and alerts are written before feature code ships
- [Service Level Objectives](service-level-objectives.md) — MDD embeds SLO thinking into the development workflow; SLO definitions precede go-live
- [Test-Driven Development](test-driven-development.md) — MDD is the observability analog of TDD — define what healthy looks like before building
- [Structured Logging](structured-logging.md) — structured logs are the observability layer designed alongside feature code in MDD
- [Golden Signals](golden-signals.md) — golden signals (rate, errors, duration, saturation) provide the framework for what to instrument in MDD

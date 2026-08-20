---
id: synthetic-monitoring
tags: [pattern, observability, reliability]
surfaces-at: [nfr-requirements, infrastructure-design]
related: [health-dashboards, service-level-objectives, metrics-and-alerting, alerting-fatigue]
complexity: foundational
---

# Synthetic Monitoring

## What It Is
The practice of probing a system at regular intervals from outside using scripted transactions — simulating real user interactions to verify availability, performance, and correctness proactively. Unlike reactive monitoring (which alerts after real users experience problems), synthetic monitors detect issues before or at the same time as users — often catching problems in off-peak hours when real traffic is low. Examples: HTTP health checks, scripted browser journeys (login, add to cart, checkout).

## When to Apply
- Any externally-facing service where availability is a business requirement
- Critical user journeys where you want proactive alerting before real users report issues
- Post-deployment verification — synthetic checks confirm the new version is healthy
- Geographic availability monitoring — run probes from multiple regions to detect regional outages

## When Not to Apply
- Internal services not accessible from probe networks (use internal health checks instead)
- As a replacement for real user monitoring — synthetics miss the long tail of real user paths

## Key Concepts
- **HTTP Check**: The simplest synthetic monitor — send an HTTP request to a URL, verify response code and optionally response body. Run every 30-60 seconds from multiple locations
- **Scripted Browser Monitor**: Playwright or Selenium-based probes that execute a full user journey in a headless browser — login, search, purchase. Catches JavaScript errors and flow regressions
- **API Transaction Monitor**: Structured HTTP sequence (login → get token → call API → verify response) that verifies end-to-end API correctness
- **Multi-Region Probing**: Running probes from multiple geographic locations — identifies CDN routing issues, regional outages, and latency disparities
- **Probe Frequency**: HTTP checks: every 1 minute. Browser transactions: every 5-10 minutes (expensive). Balance frequency against cost
- **SLA Reporting**: Synthetic monitoring data feeds availability reports and SLO dashboards — uptime % calculated from probe pass/fail history
- **Datadog Synthetics, Checkly, New Relic Synthetic Monitoring**: Managed synthetic monitoring platforms — no infrastructure to manage
- **Private Locations**: Probes deployed inside your VPC to monitor internal services not reachable from the public internet

## In Practice
Method deploys synthetic monitoring for all production external services using Datadog Synthetics or Checkly. Standard setup: HTTP checks every minute on health endpoints, scripted API transaction monitors every 5 minutes for critical flows, browser monitors every 10 minutes for key user journeys. Alerts page on-call on 2 consecutive failures. Multi-region checks detect CDN/routing issues.

## Engineering Knowledge
💡 **Engineering Knowledge — Synthetic Monitoring**: Don't wait for users to tell you the system is down. Synthetic monitors probe your service continuously — HTTP checks every minute, scripted API transactions every 5 minutes, browser journeys every 10. Alert on 2 consecutive failures to avoid noise. Run from multiple regions to catch regional issues. SLO uptime calculations should be driven by synthetic probe data, not just server-side metrics. Use Datadog Synthetics or Checkly. → `engineering-knowledge-repository/observability/synthetic-monitoring.md`

## Related Entries
- [Health Dashboards](health-dashboards.md) — synthetic monitoring feeds availability indicators on health dashboards
- [Service Level Objectives](service-level-objectives.md) — SLO availability calculations use synthetic probe data
- [Metrics and Alerting](metrics-and-alerting.md) — synthetic check results feed the alerting pipeline
- [Alerting Fatigue](alerting-fatigue.md) — multi-failure thresholds for synthetics prevent false-positive alert noise

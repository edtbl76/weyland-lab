---
id: real-user-monitoring
tags: [pattern, observability, frontend, performance]
surfaces-at: [application-design, infrastructure-design]
related: [synthetic-monitoring, web-performance, metrics-and-alerting, distributed-tracing, opentelemetry]
complexity: intermediate
---

# Real User Monitoring (RUM)

## What It Is
Collecting performance and experience metrics from actual users as they interact with the application in production — as opposed to synthetic monitoring, which simulates user interactions from controlled environments. RUM captures Core Web Vitals (LCP, INP, CLS), JavaScript errors, API response times, and user journey completion rates from real browsers, real devices, real networks, and real geographic locations. This provides ground truth about what users actually experience, including the long tail of slow devices and poor network conditions that synthetic tests miss.

## When to Apply
- Any user-facing web application where performance impacts user experience or business metrics
- After Core Web Vitals optimization work — to verify improvements in production, not just in Lighthouse
- When synthetic monitoring passes but users are reporting slowness
- Applications with geographically distributed users or diverse device types

## Key Concepts
- **RUM vs. Synthetic Monitoring**:
  - *RUM*: Real users, real conditions. Captures the actual distribution of experiences including slow devices and network variability. Cannot run before production; no control over test conditions
  - *Synthetic*: Controlled, repeatable test scenarios from fixed locations. Can run pre-production (CI gates). Consistent baselines; misses real-world variability
  - Both are needed: synthetic for CI gates and regression detection; RUM for production truth
- **Core Web Vitals in Production**: The `web-vitals` JavaScript library (Google) measures LCP, INP, and CLS from real browsers and reports them to an analytics endpoint. Google Search Console displays CWV data from the Chrome UX Report (CrUX), a large-scale RUM dataset from Chrome users
- **Error Tracking**: JavaScript errors, unhandled promise rejections, and stack traces captured from user sessions. Tools: Sentry, Datadog RUM, Rollbar. Essential for catching errors that escape test coverage — real users hit edge cases tests never simulate
- **Session Replay**: Record user sessions as video-like playback for debugging UI issues. Sentry Session Replay, FullStory, LogRocket. Privacy considerations: mask PII (form inputs, personal data) before capturing
- **Performance Monitoring Tools**:
  - *Datadog RUM*: Full-stack; correlates frontend metrics with backend traces. Integrates with Datadog APM for end-to-end request tracing
  - *Sentry*: Error tracking + performance monitoring + session replay. Strong JavaScript error capture. Popular with frontend teams
  - *New Relic Browser*: Similar to Datadog RUM; part of New Relic's full-stack observability platform
  - *web-vitals library + custom analytics*: Lightweight; report CWV to your own analytics pipeline
- **Percentile Metrics**: RUM data is non-normal — the p75 and p95 are more meaningful than the mean. A page may load in 500ms for 80% of users but 5 seconds for 20%. Mean hides the tail. Core Web Vitals targets are set at p75
- **Geographic and Device Segmentation**: RUM enables segmenting performance by country, device type, browser, and connection speed. Mobile users on 3G in Southeast Asia have a fundamentally different experience than desktop users on fiber in the US. Segmentation identifies where to prioritize optimization
- **Funnel Analysis**: Track completion rates through critical user journeys (checkout, signup, feature adoption). Drop-offs in the funnel can correlate with performance degradation or JS errors — RUM surfaces this connection
- **Alerting on RUM Data**: Alert when p75 LCP exceeds threshold or JS error rate spikes. RUM metrics are noisier than synthetic — use rolling averages and relative thresholds (e.g., alert when error rate is 3x baseline) rather than absolute thresholds

## In Practice
Method integrates Sentry for JavaScript error tracking and performance monitoring on all frontend applications. The `web-vitals` library reports CWV to Datadog for alerting. Core Web Vitals p75 thresholds are monitored in Datadog dashboards. Session replay is enabled with PII masking. Geographic segmentation in Datadog surfaces regional performance issues. Sentry error tracking is the primary signal for post-deploy regression detection.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Real User Monitoring**: Lighthouse scores and synthetic tests tell you how fast your app is in a controlled environment. RUM tells you how fast it is for actual users. Always measure CWV at p75 (not mean) in production via RUM — the mean hides the tail that your slowest 25% of users experience. Correlate JavaScript errors from Sentry with deployment events — a spike in errors after a release is the first signal of a regression before user complaints arrive. Session replay is invaluable for debugging UI issues that are hard to reproduce locally; mask PII before enabling. → `engineering-knowledge-repository/real-user-monitoring.md`

## Related Entries
- [Synthetic Monitoring](synthetic-monitoring.md) — synthetic monitoring complements RUM with controlled pre-production and baseline testing
- [Web Performance](web-performance.md) — RUM validates web performance optimization work in production
- [Metrics and Alerting](metrics-and-alerting.md) — RUM metrics feed into alerting pipelines for regression detection
- [Distributed Tracing](distributed-tracing.md) — Datadog RUM correlates frontend performance with backend trace data for end-to-end visibility
- [OpenTelemetry](opentelemetry.md) — OpenTelemetry browser instrumentation provides vendor-agnostic RUM data collection

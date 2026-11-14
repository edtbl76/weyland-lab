# Don't adopt Sentry SaaS

## Status

accepted

Date: 2026-11-13

## Context and Problem Statement

B53 proposed comparing Sentry's free tier with GlitchTip.

## Decision Drivers

* Only adopt what fills a real gap.
* Keep application errors on the LAN where it costs nothing to.

## Considered Options

* Keep GlitchTip and the existing stack
* Sentry SaaS (free tier)

## Decision Outcome

Chosen option: Keep the existing stack (owner, 2026-11-13: "Kill it."), because everything Sentry adds is already covered (OTel tracing, Pyroscope, the cron-freshness checks, Port deployments, Grafana and U14 alerting), and its one real gap, suspect commits, falls out of B243's overnight triage.

### Consequences

* Good, because there is no second error pipeline.
* Neutral: session replay is moot without a real frontend with users.

## More Information

Backlog B53 (won't do), Linear EMA-42.

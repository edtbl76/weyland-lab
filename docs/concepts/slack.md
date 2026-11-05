# Slack — the lab's feed (B184)

The lab adopted a **free Slack workspace** on 2026-11-04, partly as a demo surface ("how this looks in a real org's
chat") and partly as a readable feed of what the platform is doing. **Telegram remains the only pager.** Runbook:
[runbooks/slack.md](../runbooks/slack.md).

## The constraint that shaped everything

The free plan (Slack help center, verified 2026-11-04) allows **at most 10 installations** (third-party or custom apps), keeps 90 days of
history, and has no workflows, canvases or lists. The lab is also **LAN-only**: Slack cannot call into it, so slash
commands, buttons and Events-API apps hosted in the lab are out. That leaves two mechanisms:

| Mechanism | Slot cost | Used for |
|---|---|---|
| **Incoming webhook** of one custom app, `weyland`, one webhook per channel | **1 slot in total**, shared by every webhook tool | Alertmanager, Uptime Kuma, Argo CD, Woodpecker, GlitchTip |
| A vendor's own Slack app (SaaS ↔ Slack, never touching the lab) | 1 slot each | Linear, GitHub |

**3 of 10 slots used.** One is reserved for the incident-tool phase (below).

## The audit (2026-11-04)

Each tool was researched against its deployed version's official docs. Claims no source confirmed were marked
unverified rather than assumed. The one material unverified claim, whether the GitHub app works on free Slack, was
settled by installing it: it does.

| Tool (version) | Slack mechanism | Slots | Verdict | Why |
|---|---|---|---|---|
| Alertmanager 0.32.2 | `slack_configs`, webhook via `api_url_file` | 0 | **adopt** → `#alerts` | the alert feed; the secret stays out of config |
| Uptime Kuma 1.x | Slack notification type (webhook) | 0 | **adopt** → `#alerts` | up/down beside the Prometheus alerts |
| Argo CD 3.4.4 | built-in notifications, generic `webhook` service | 0 | **adopt** → `#deploys` | sync failures and degraded health. Not `on-deployed`: every push re-syncs ~83 apps |
| Woodpecker 3.18 | none built in; our own `curl` step | 0 | **adopt** → `#deploys` | failed pipelines; no third-party plugin needed |
| GlitchTip 6.2 | alert recipient "Webhook" (Slack-compatible) | 0 | **adopt** → `#errors` | new-error alerts per project |
| Linear | Linear Slack app | 1 | **adopt** → `#linear-updates` | completed/canceled, triage, project + initiative updates |
| GitHub | GitHub app for Slack | 1 | **adopt** → `#github` | issues, PRs, commits, releases |
| Grafana 13.0.1 | contact point (webhook) | 0 | skip | the lab's alerts are Prometheus rules, not Grafana-managed |
| Dagster 1.13.14 | `dagster-slack` (bot token) | 0–1 | skip | failures already reach Alertmanager (freshness watchdog) and so `#alerts` |
| DataHub 1.6.0 | `datahub-actions` Slack action (bot token) | 1 | skip | metadata chatter is not worth a slot |
| SonarQube Community 26.x | none in Community Build | — | skip | Slack is a paid-edition feature |
| MLflow 3.x, Langfuse v3 | no native Slack (webhooks need a relay) | 0 via n8n | skip | no audience for registry/prompt events |
| Keycloak 26.1 | none (community listener only) | 1 | skip | no need |
| Unleash 8.0.1, Port | Slack app / webhook | 0–1 | skip | flag and catalog events have no audience here |
| n8n 2.29 | Slack node / HTTP | 0 | relay only | the fallback for any tool without Slack output |
| Figma | Figma Slack app | 1 | skip | B183 is parked |
| Axolo | own app, a channel per PR | 1 | skip | per-PR channels coordinate a team; the lab has one reviewer |
| Graph, Alkemi, Blocks (Linear directory) | own apps | 1 each | skip | Graph needs a paid Slack; the others are unverified or paid |
| OneUptime CE | own app; Slack must reach it over public HTTPS | 1 | **ruled out** | inbound-only design, and it refuses Socket Mode |

## Routing: Telegram pages, Slack is the feed

The backlog's rule: overlap is fine where it earns it, but **the same alert must never simply ping twice**. Slack
posts carry no @mentions, so they don't push to a phone. They are a record you read, not a page.

| Alert class | Telegram (pager) | Slack | Linear |
|---|---|---|---|
| critical | yes | `#alerts` | an incident issue (U14) |
| warning / info / no severity | yes | `#alerts` | — |
| Uptime Kuma monitor down | yes (Kuma's Telegram notifier) | `#alerts` | — |
| Watchdog (dead-man's switch) | — (healthchecks.io) | — | — |
| InfoInhibitor | — | — | — |
| Argo CD sync failed / degraded | — | `#deploys` | — |
| CI pipeline failed | — | `#deploys` | — |
| GlitchTip new error | — | `#errors` | — |

## Already met elsewhere

- **Alert → a deduplicated Linear issue** was a B184 requirement. U14 met it: n8n `alert-to-linear`, live
  2026-11-04. An incident tool must not duplicate it.

## Still to decide (the incident phase)

The incident tool and the exercised pager rotation are the next phase: Keep (OSS, webhook), Runframe (hosted, free
to 5 users, 1 slot), or an Alertmanager route that alternates receivers. Cost that matters most is RAM on mother.

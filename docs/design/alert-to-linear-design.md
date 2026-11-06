# Alert → Linear incident — design record (U14)

**Status: APPROVED and BUILT (2026-11-04), live.** Owner approvals: the re-scope ("sounds good to me", 2026-11-03),
the build ("yes, start!"), incident numbering ("Give it a B/U number"), and the credential name. Linear EMA-16.
Runbook: [runbooks/alert-to-linear.md](../runbooks/alert-to-linear.md). Flow:
[diagrams/flow-alert-to-linear.md](../diagrams/flow-alert-to-linear.md).

## Problem

A critical alert went to Telegram, and nothing recorded whether it was seen, acted on, or resolved (the B44 finding).
The estate had no memory of incidents: no timeline, no history of what fires repeatedly, nothing to query. Grafana
OnCall would answer this but is held for hardware (four always-on workloads). Separately, n8n had run zero active
workflows for months and had twice been a retirement candidate.

Five critical alerts fired in the 30 days before this was built (Prometheus, read 2026-11-03). The volume is low, so
an issue per incident is readable, not noise.

## ADR-1 — n8n is the tool, not Dagster, Alertmanager alone, or OnCall

**Context.** The job is event-driven glue: a webhook arrives and a SaaS is touched. The lab's options were n8n
(running, idle), Dagster (running, schedule/asset-driven), a native Alertmanager integration, or Grafana OnCall.

**Decision.** n8n.

| Option | Event-driven | Runs today | Stateful dedup/close | Cost | Verdict |
|---|---|---|---|---|---|
| **n8n webhook workflow** | yes, native | yes, idle | yes (GraphQL lookup) | $0, no new workload | **chosen** |
| Dagster sensor/job | no: polls, minutes of lag, a run per alert | yes | yes | $0 | wrong shape: Dagster is batch. It got the scheduled Linear digest instead (B237) |
| Alertmanager → Linear directly | Alertmanager has no Linear receiver; the generic webhook can't speak GraphQL or dedupe | — | no | — | not possible without glue |
| Grafana OnCall | yes | no | yes | 4 always-on workloads | held for hardware (B44) |
| A small custom service | yes | no | yes | new image, CI, ServiceMonitor, DR | more to own than an n8n workflow |

**Consequences.** n8n becomes a dependency on the alert path, but only for the record: Telegram never depends on it
(ADR-2). n8n gains a live job, and its retirement question is settled. The workflow is UI-editable, so git can drift
from live; the runbook's export step closes that gap.

**Alternatives rejected.** Dagster (wrong execution model); a custom service (cost of ownership); OnCall (hardware).

## ADR-2 — Two routes: incident with `continue: true`, then an explicit critical → Telegram

**Context.** In Alertmanager a matching child route claims the alert. `continue: true` only lets the walk go on to the
next sibling, and the parent's default receiver fires only when NO child matched. Adding just an incident route with
`continue: true` would have silently stopped Telegram from paging criticals.

**Decision.** Route 1: `severity="critical"` → `linear-incidents`, `continue: true`. Route 2: `severity="critical"` →
`telegram`. Proven with `amtool config routes test` v0.32.2 (the cluster's version): critical goes to
`linear-incidents,telegram`, warning to `telegram`, and Watchdog/InfoInhibitor are unchanged.

**Consequences.** Telegram's behaviour is byte-for-byte what it was, and the incident path is purely additive. A
future change to the critical route must keep both routes. The runbook carries the `amtool` proof command.

**Alternatives rejected.**
- A webhook inside the `telegram` receiver: it couples the two; a failing n8n would mark the whole receiver failed and
  retry Telegram too.
- n8n forwarding to Telegram: it makes n8n the pager, the opposite of the goal.

## ADR-3 — Dedup by fingerprint marker in the description; reopen within 24 h

**Context.** Alertmanager re-sends a firing group every `repeat_interval` (4 h) and re-sends resolved notifications.
Alerts flap. The same alert must map to one issue.

**Decision.**
- **The key:** the Alertmanager fingerprint (a hash of the label set), written as the last line of the description,
  `alert-fingerprint: <fp>`.
- **The lookup:** label `incident` + description contains the marker + state not Canceled/Duplicate.
- **The rules:**
  - firing + open → no-op;
  - firing + closed less than 24 h ago → reopen + comment;
  - firing + none (or closed earlier) → create;
  - resolved + open → comment + Done;
  - anything else → no-op.

**Consequences.**
- Idempotent under retries: a create followed by a lost response is found on retry.
- Editing the marker line out of an issue breaks its dedup; this is documented in the runbook's troubleshooting.
- Canceling an issue opts it out, so the next firing opens a fresh one; this is deliberate and documented.
- Live proof: EMA-329 re-fired and was reopened, not duplicated.
- **Known limit, Linear's read-after-write lag.** The filtered `issues` lookup can return an issue's state from before
  a write made less than a second earlier. In the 2026-11-04 re-rehearsal, a `resolved` sent immediately after a
  reopen read the pre-reopen state and did nothing; the same `resolved` about 30 s later closed the issue. Alertmanager
  never sends that fast: a group's notifications are `group_interval` (5 min) apart, and a reopen and its resolve are
  minutes apart. The only exposure is a retry landing within a second of a create that succeeded, so no delay was
  added.

**Alternatives rejected.**
- **Linear attachments keyed by URL** (Linear's own idempotency): the alert's `generatorURL` is not unique per
  fingerprint, and it adds a second write per create.
- **An n8n-side store** (static data or a table): it would be a second source of truth, lost with n8n's PVC (which
  has no backup by decision, ADR-6); Linear already holds the state.
- **Always creating a new issue on re-fire:** flapping would spam issues.

## ADR-4 — Incidents live in Weyland Lab, titled `U14 incident — …` — SUPERSEDED 2026-11-06

> **Superseded (B189, owner decision):** incidents now live in project **Weyland Auto-Filed** (initiative
> `Automation`), the home for every issue a machine files and closes. The trigger was Trunk's flaky-test tickets, which
> can't carry a B/U number (no title template). One rule for all machine-filed issues beats a number for one source
> and an exemption for another. The 8 existing incidents moved; the workflow's `projectId` now points there. The
> `U14 incident —` title stays but is no longer load-bearing, and the lowest-EMA join fix stays (it is correct in
> general). The original decision, kept for the record:


**Context.** `check-linear-sync.sh` check F fails any Weyland Lab issue whose title carries no B/U number. Options:
a separate project/initiative outside the guard's scope, a guard exemption by label, or numbering.

**Decision (owner: "Give it a B/U number").** Titles start with `U14`, so every incident is accounted to the work that
creates it. That exposed a guard defect: the guard joined a number to the FIRST issue carrying it in snapshot order, so
a newer open incident could become U14's join and read as "backlog DONE, Linear open". Fixed: the lowest EMA number
wins. A bats test was written red first.

**Consequences.**
- Incidents sit beside the work in Weyland Lab views, filterable by the `incident` label and Urgent priority.
- The guard has no special case, and its join is now deterministic. Live: `check-linear-sync.sh` OK with 4 incidents
  present.

**Alternatives rejected.**
- A separate project: one more project/initiative to keep in parity (checks G/H), and incidents hidden from the lab's
  view.
- A label exemption in the guard: a special case in a 919-line guard.

## ADR-5 — The front door is a NetworkPolicy, not a shared secret

**Context.** n8n webhooks carry no authentication. Before U14, any pod in the cluster could call n8n's Service, and
this webhook now writes to Linear. B209's rule: every write surface is authenticated or unreachable.

**Decision.** NetworkPolicy `n8n-front-door-only`: ingress on 5678 only from Traefik (kube-system, the
forward-auth'd UI) and the Alertmanager pods (monitoring). It is pinned by `write-surface-netpol.bats`, and
`check-write-surfaces.sh` credits it.

**Consequences.**
- No secret to mint, store, rotate, or leak.
- Alertmanager's config stays free of credentials, which matters because the repo is public.
- The webhook's URL is not a secret.

**Alternatives rejected.**
- A header-auth token on the webhook: n8n's Header Auth on a webhook needs a credential, and Alertmanager's
  `http_config.authorization.credentials_file` needs a Secret mounted. That's two places to keep in sync, for a caller
  set a NetworkPolicy already pins.
- Istio AuthorizationPolicy: neither namespace is meshed.

## ADR-6 — The Linear key is an n8n credential; n8n's DB is not backed up

**Context.** The workflow needs a Linear key with Read + Write. n8n stores credentials encrypted in its SQLite DB.
The alternative is a k8s Secret exposed as an env var and read through `$env`.

**Decision.** An n8n Header Auth credential named `Linear write key`, created by the owner in the UI. Only its name is
in git. The import binds it by name.

There is no backup of n8n's SQLite. The workflow is in git, the one credential is re-entered from Linear, and
execution history is accepted as lost (`dr.md` n8n row).

**Consequences.**
- Restore is three owner steps, tested in a fresh n8n and twice live.
- The binding rule is strict (n8n 2.29 `replaceInvalidCredentials`): exactly ONE credential of that exact name and
  type in the workflow's project. Anything else leaves a dangling reference, and every run then 500s. The first live
  install hit this (the credential was named differently from the file), and so did a write-only key. Both are now in
  the runbook, with a usage-badge check.

**Alternatives rejected.**
- A Secret via `$env`: it needs `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, which exposes every env var, including
  `N8N_ENCRYPTION_KEY`, to any workflow.
- Backing up the SQLite: it holds one re-enterable credential and disposable history; a nightly job would protect
  nothing that git and Linear don't already hold.

## ADR-7 — Fail closed: every step's error output answers 500

**Context.** Two n8n 2.29 behaviours were found in the rehearsal:
- in `lastNode` response mode, a run with nothing to do (no criticals, a repeat) answers **500**, so Alertmanager would
  retry and alert forever on success;
- in `responseNode` mode, a run that **errors** answers **200**, so every failure would be invisible.

Linear also answers a refused GraphQL write with HTTP 200 and an `errors` array.

**Decision.**
- `responseNode` mode.
- Every working step has an error output into `Respond failure` (500).
- A `Verify` step throws unless every write reports `success: true`.
- A no-op run reaches no Respond node, which n8n answers 200.

**Consequences.**
- Any failure becomes a 500. Alertmanager retries, `alertmanager_notifications_failed_total{integration="webhook"}`
  counts it, and `AlertmanagerFailedToSendAlerts` (warning) reaches Telegram.
- Proven live: the install-window failures fired it.
- Rehearsal: a garbage payload and an invalid key both answered 500.

**Alternatives rejected.**
- `onReceived` (an immediate 200): it hides every failure.
- An n8n error workflow posting to Telegram: a second alert path to own, when Alertmanager already measures delivery.

## Observability (Pillar 6 four signals)

| Signal | Coverage |
|---|---|
| Metrics | n8n's own `/metrics` is off. The functional signal is Alertmanager's per-integration counters (`alertmanager_notifications_total` / `_failed_total{integration="webhook"}`), already scraped. Grafana **Alertmanager / Overview** (`alertmanager-overview`) charts them per integration: the `webhook: Notifications Send Rate` panel (sent vs failed) and `webhook: Notification Duration` (p50/p99, which is n8n's response time). |
| Alerts | `AlertmanagerFailedToSendAlerts` (warning) when deliveries fail; blackbox probe of `n8n.weyland.lab` (added in this DoD) for the front door, and `IngressNotProbed`, which now pages for any ingress left unprobed. |
| Logs | n8n container logs in Loki (`{namespace="n8n"}`), confirmed. Execution detail is in n8n's Executions view, and Alertmanager logs each failed response body. |
| Traces / profiles | N/A: a single hop, and n8n is not a profiling target. |

## What was deliberately left out

- Assigning incidents, or paging from Linear: Telegram is the pager.
- Severities below critical: warnings would flood Linear.
- Enrichment (logs, pods): that's the operator's incident sweep (B45).
- Postmortems: the issue is the timeline.

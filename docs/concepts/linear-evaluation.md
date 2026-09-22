# Linear — feature evaluation (B119)

> The "master the tool" pass for Linear, the same treatment done for Port (B60) and DataHub (B80).
> Method: walk Linear's features **one at a time, against real workspace data** (pulled live via the
> Linear MCP), and for each land an **adoption decision** for the lab's workflow. The lab is **solo, $0,
> LAN-only**; **`docs/backlog.md` is the durable, ordered record** and **Linear is the working/reasoning
> + status surface** ([[linear-status-source-of-truth]]). A feature is worth adopting only if it earns its
> place under those constraints — collaboration features that assume multiple people usually do not.
>
> This doc is a **living record**: each feature gets a row in the table below and a detail section as we
> get to it. B119 closes when the walk is complete and the adopted set is settled.

## Adoption decisions (running)

| Feature | Verdict | The decision |
|---|---|---|
| **Inbox / notifications** | **ADOPT WITH LOW TRUST — an event *pointer*, not a state source** | Keep the GitHub↔Linear connection ON for surface-consolidation (Linear = GitHub dev events, Port = ops events). But the Inbox mirrors the *event* ("review requested"), not the PR's *state* (mergeable / stale / superseded) — so **GitHub remains the source of truth for PR state, and nothing is actioned from the Inbox's signal alone.** Same discipline as issue drift: verify mechanically, don't trust the tool's view. |
| **Workflow states** | **KEEP the 7 states as-is — a `Parked` *state* was REJECTED; "on hold" is a label, not a state** | The 7 EMA states (Backlog · Todo · In Progress · In Review · Done · Canceled · Duplicate) cover the lifecycle. Held/deferred items *are* invisible in Linear (the binary sync guard collapses HELD/BLOCKED/DEFERRED → "open"; the B86 pattern) — but a `Parked` **state** is the wrong fix: a workflow state is *mutually exclusive*, so parking an issue overwrites the lifecycle position it was parked *from*, and un-park becomes ambiguous. "On hold" is an orthogonal **facet**, so it belongs on a **label**. Shipped instead (2026-09-22): `parked:held` (external blocker) + `parked:deferred` (deliberate), tagged on B134/B150/B86 — each keeps its real state *and* priority. Fully MCP-automatable; no Linear-UI hand-off. |

## Inbox / notifications

**Real data (MCP `get_notifications`, 2026-09-21):** the *entire* inbox is **21 notifications, 100%
`pullRequestReviewRequested`, every one a dependabot dependency-bump PR** surfaced via the GitHub
integration. Zero issue-assignment / mention / comment / status-change notifications. Nearly all share
one identical `readAt` timestamp (a single bulk "mark all read"); the few with distinct `readAt` are the
ones actually engaged.

**Why the feed looks like this:** Linear's Inbox is a *collaboration* feed — assignments, @mentions,
comments, review hand-offs *between people* — and Linear suppresses self-triggered notifications. In a
**solo** workspace none of those fire, so the only traffic is from **external actors**: here, dependabot
via the GitHub integration.

**Verdict — ADOPT WITH LOW TRUST — an event *pointer*, not a state source.** The consolidation value is
real: **aggregation collapses surfaces** — GitHub-origin notifications landing in Linear means one fewer
place to monitor (GitHub's own notifications tab), a net reduction for a solo operator across weyland +
Stud.IO's many repos. So keep the connection. But a decisive caveat emerged on contact with real data
(below): the Inbox mirrors the *event*, not the *state*, so it cannot be trusted as a source of truth.

**The decisive finding — the Inbox is an event pointer, not a state source.** Actioning the weyland slice of
the inbox exposed how thin the mirror is. Of 21 notifications only 3 mapped to open weyland-lab PRs, and
against `main` those were: **#80** quic-go — clean / current / safe; **#72** soupsieve — wanted but the
branch is **stale** and would clobber main's curated `requirements.txt`; **#63** aiohttp — **stale and
regressive**, its bump already satisfied on main while merging it would *downgrade* `cryptography` 50→48
(reintroducing CVE-2026-69247/69249) and `mlflow` 3.15.1→3.14.0. **The most dangerous item presented in the
inbox identically to the safe one** — "dependabot requested your review," with no currency or quality signal.
The Inbox aggregates the *existence* of PRs, never their *actionability*.

**Why the sync can't be trusted, and the discipline that follows.** This is the lab's recurring pattern:
never trust a tool's own view of external state — verify mechanically. Issue-state drift is not trusted to
Linear's UI, it is guarded by `check-linear-sync.sh` ([[linear-status-source-of-truth]]). The Inbox has no
equivalent guard over GitHub PR state, so it is a **low-trust event feed**. **GitHub (or a mechanical check)
remains the source of truth for PR state, and nothing is merged/closed on the Inbox's signal alone** — proven
here, where "review requested" would have led straight into a silent security downgrade.

**The division of labor (decided):**

- **Linear Inbox = code/dev notifications** — GitHub PR + linked-issue activity across all repos, with the
  inbox lifecycle (snooze bumps for later, archive done ones, priority). Plays to Linear's native
  GitHub-integration strength. **Keep git connected to Linear.**
- **Port = operational aggregator** — CI outcomes (`ci_pipeline`, B63), GlitchTip errors (`glitchtip_issue`),
  uptime — already ingested via webhook. A *different class* of event; Port's catalog/dashboard shape fits
  runtime state, Linear's inbox shape fits actionable dev items. Neither is forced into the other's grain.

**Root-cause / standing hazard (bigger than these 3 PRs).** In a **LAN = no-webhooks** + **Woodpecker
post-merge CI** + **hand-remediated-CVE** setup, dependabot branches sit and go **stale**, silently carrying
pre-remediation resolutions. Merging accumulated stale PRs is therefore a regression trap — and **blanket
dependabot auto-merge is UNSAFE** (it would have applied #63's cryptography/mlflow downgrade unattended).

**Resolved — and it answered the "keep Linear updated vs. move the notifications" question.** The right
workflow is not to make Linear's mirror smarter but to **keep the source clean so any mirror is trustworthy
by construction**. That routine shipped as `scripts/check-pr-lifecycle.sh` (the unbuilt resolution half of
**B131**): it classifies every open managed PR (STALE / SUPERSEDED / MERGEABLE / NEEDS-HUMAN) and, on
`--apply`, `@dependabot recreate`s the stale ones (re-cut against current main — cannot regress) and closes
superseded ones, never merging. With the PR set kept current + minimal, the GitHub↔Linear mirror is accurate
without any Linear-side automation, and the residual reaching the Inbox is only genuinely-actionable items.
So the Inbox stays adopted (low-trust pointer), the reconciler is the accuracy mechanism, and the surface
question is moot because the volume is near-zero. See [runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md)
§ "Resolving open PRs".

**Latent value to revisit:** the Inbox is also the delivery surface for **subscription** notifications and
**automation / SLA** triggers. It is empty of that value *today* only because nothing the lab runs emits to
it — reconsider its weight if later features (automations, SLAs, a parked/stale-issue rule) start feeding it.

## Workflow states

**Real data (MCP `list_issue_statuses`, EMA team, 2026-09-22):** **7** states — `Backlog` · `Todo` ·
`In Progress` · `In Review` · `Done` · `Canceled` · `Duplicate`. So the normal lifecycle *is* covered; the
B119 evidence's "only Backlog / Done / Canceled" was wrong (corrected here). What's **missing** is a
**Parked / On-Hold** state.

**The gap is real — the sync guard shows why.** `check-linear-sync.sh` reconciles every backlog
item to a **binary** `done | open` (terminal = `completed|canceled|duplicate`; everything else = open). So the
backlog's rich status vocabulary — **HELD FOR HARDWARE** (B134, B150), **BLOCKED-BY**, **PARKED** (store-scaler
sleep), **DEFERRED** (B86), MOOT, WON'T-DO, PARTIAL — all collapses to "open." In Linear, a held-for-hardware
item is indistinguishable from a not-yet-started one. That is exactly the B86 failure mode: a decided-but-deferred
item had no signal that said so.

**First decision — ADD a `Parked` state — was REJECTED on contact with the operator (2026-09-22).** The initial
verdict here was "add one backlog-type `Parked` state." That was wrong, and the reason is worth keeping: **a
workflow state is mutually exclusive** — an issue is in exactly one. Moving a held item to `Parked` therefore
*erases where it was* when it was parked. A held-in-`In Review` item and a held-before-`Todo` item both flatten
to the same bucket, and on un-park the correct return state is ambiguous. The state destroys orthogonal
information (lifecycle position) to record one bit (held / not-held). (A `Parked` *project* status — a different
screen, `Settings → Project statuses` — is even further off: it parks the whole container and severs the
originating-project link. Neither the issue-state nor the project-state route is right.)

**Correct mechanism — a label facet, not a state.** "On hold" is not a lifecycle *phase*; it is a *facet* that
can co-exist with any phase. Facets belong on **labels** (additive, non-exclusive), not the state machine
(exclusive, lossy). A `parked:*` label leaves the issue's real state and priority intact and additionally carries
the hold + its reason. Bonus over the state path: labels are fully MCP-automatable (`create_issue_label` +
`save_issue addLabels`, append-only) — no Linear-UI hand-off. This is the **state-vs-facet** rule: whenever adding
a value would *overwrite* an orthogonal fact, it is a facet (label), not a state.

**Shipped 2026-09-22 (two workspace labels, color `#78828F`):**
- **`parked:held`** — on hold behind an external blocker the lab can't act on now (hardware, an RMA, an upstream
  issue). Applied to **B134 / EMA-195** (HELD FOR HARDWARE) and **B150 / EMA-186** (mainboard RMA, gated on B149).
- **`parked:deferred`** — deliberately deferred; a decision, not a blocker. Applied to **B86 / EMA-76**
  (REOPENED / DEFERRED).

Each issue kept its priority label and its `Backlog` state (verified in the `save_issue` response) — the
orthogonality proof. The specific *why* still lives in the `docs/backlog.md` entry; the label is the queryable
facet, the backlog is the prose. Terminal mappings are unchanged: WON'T-DO / MOOT → `Canceled`, DONE → `Done`.

**Verdict — KEEP the 7 states as-is; do NOT add `Parked`.** The lifecycle set is complete. The hold/deferred
visibility gap is closed by the `parked:*` label facet instead. This also settles part of the **Labels** feature
(next on the walk): labels are the right home for orthogonal, queryable facets — priority is the open question there.

**Not-yet-tagged candidates (follow-up audit, not done here):** the operator named exactly B134/B150/B86, so only
those were tagged. Audit later for a `parked:*` fit — e.g. any BLOCKED-BY relation (B80), the parked store-scaler
sleep — before tagging.

**Optional enforcement (follow-on):** teach `check-linear-sync.sh` to match a backlog `HELD|BLOCKED|DEFERRED`
marker to a `parked:*` label and flag drift — upgrading the guard from binary `done|open` to `done|parked|open`.
Deferred until the facet has proven itself.

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
| **Priority — field vs. label** | **ADOPT the native `priority` field as sole SoT; RETIRED the `High`/`Medium`/`Low` labels (done 2026-09-22)** | Priority is a single exclusive value → a **field**, not a facet (the mirror image of the parking call). It was carried *twice* — the native field **and** redundant priority labels — which guarantees drift: **28 of 224 issues disagreed** (13 hard contradictions + ~15 field-unset-but-labelled), *all* in terminal `Done`/`Canceled` items; the open queue was already 100% field-consistent. Decisive dependency check: `check-linear-sync.sh` already treats the **backlog** tier as SoT and compares the Linear **field** (`n.get("priority")`), never the label — so nothing depended on it. Retired `High`/`Medium`/`Low`/`Maturity`; the field (governed by `docs/backlog.md`, the Gold standard) is the only priority mechanism. Labels become a pure **facet** space: type (`Tech Debt`/`Bug`/`Feature`/…) + operational (`parked:*`). |
| **Projects / Initiatives / Milestones** | **Projects: KEEP (already core, guard-enforced). Initiatives: DON'T ADOPT. Milestones: skip.** | Projects are the product separator (`Weyland Lab` / `Stud.IO` / `rogueone Hardware`), enforced by `check-linear-sync` check B (no project-less open issue). **Initiatives** (0 defined) sit *above* projects to group many projects toward a themed goal — nothing for that layer to organize at a solo 2–3-product scale; projects are already the top level, so an initiative would be empty ceremony. **Milestones** exist only on the `Service Transformation` project (as a course TOC); real work is sequenced by backlog B-numbers + Linear **epics** (parent issues), so milestones would duplicate that with a weaker mechanism. Container-hierarchy rule: adopt the nesting level with real fan-out (Project→Issue), skip levels without it (Initiative→Project, Project→Milestone). `Service Transformation` (0 issues, seeded milestones) is a **planned track the operator keeps — explicitly NOT to be archived.** |
| **Reviews (code diffs)** | **ADOPT as a low-trust cross-repo triage QUEUE — NOT the decision surface** | Linear's Reviews is the *workbench* view of the same population the Inbox only *points* at: the fleet's open dependabot PRs (100% of the 15 diffs pulled, across 5 repos), all requesting review, **zero ever reviewed in Linear**. Richer than the Inbox (`mergeStatus`, diff stats, threads, in-app approve) but the **same trust ceiling** — `mergeStatus: "ready"` means *mergeable*, not *safe*: #72/#63 read `ready` while `check-pr-lifecycle.sh` classified them STALE/regressive (#63 = a silent cryptography downgrade). Keep it as a cross-repo triage queue (real consolidation, free on the GitHub↔Linear connection), but the **mechanical reconciler stays the SoT for PR actionability** — nothing merged/approved on Linear's review signal alone. As of B176 that reconciler covers *every* repo the queue aggregates, so view and resolver are finally the same scope. Same discipline as the Inbox (verdict #1). |
| **Agent (coding sessions) + Skills** | **DON'T ADOPT the Agent (paid cloud, duplicates local Claude Code); DO invest in portable skills (git SoT + Bifrost registry)** | Linear's "Agent" = **coding sessions**: delegate an issue → Linear spins a coding session in its **managed cloud sandbox** (Claude Code/Codex), drafts a PR. It **costs AI credits** (not $0) and **runs in the cloud, not the LAN** — duplicating the local Claude Code workflow the lab already runs free. Fails both hard constraints → don't adopt. BUT its "skills" are just **repo files** (`skills.md` / Claude Code skills), which the lab already owns: `register_bifrost_skills.py` is the git SoT, and Bifrost **serves them as a Claude Code marketplace**. So a skill is a portable artifact with a swappable consumer — invest there ($0, LAN, local Claude Code now; the Linear Agent later if ever paid). Seeded 4 loop-skills (DoD gate, master-the-tool walk, pr-lifecycle reconcile, full-guard-suite) — executes B175. |

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

## Priority — field vs. label

**Real data (live pull of all 224 EMA issues + `scripts/check-linear-sync.sh`, 2026-09-22).** Priority was carried
**two ways**: Linear's native `priority` field (Urgent/High/Medium/Low/None — built-in, *exclusive*, sortable) *and*
redundant `High`/`Medium`/`Low` labels (+ a legacy `Maturity`).

**The model error, and it's the mirror of parking.** Priority is a single *exclusive* value, so it is field-shaped,
not facet-shaped. Parking was a facet wrongly forced into the exclusive *state* machine; priority was an exclusive
value wrongly *also* kept as a facet (label). Same state-vs-facet rule, opposite direction. Two stores for one
exclusive value is duplicated mutable state with no reconciler — it *must* drift.

**And it had drifted — 28 of 224 issues disagreed:**
- **13 hard contradictions** — both set, to *different* real priorities. E.g. **B89** field `High` / label `Low`;
  **B99** `Medium`/`High`; **B96** `Medium`/`High`; **B115** `Medium`/`High`; **B92** & **SEC-1** `Medium`/`Low`;
  **B74** `Low`/`Medium`. The drift has *no direction* (sometimes field higher, sometimes label) — the signature of
  two independently-edited copies, with no heuristic to recover which is right.
- **~15 field-unset-but-labelled** — older items where the field was never set (`No priority`) and only a stale label
  claimed a tier (B43, B50, B51, B55, B56, B58, B59, B61, B62, B111…).
- **Crucially, every drifting item is `Done`/`Canceled`.** The *open* queue is already 100% field-consistent
  (`field == label` on every open item that has a label; recent items carry the field and *no* priority label at all —
  the field already won in practice). So the drift is historical debris, not active mis-prioritization — there was
  nothing live to adjudicate.

**Decisive dependency finding — nothing depended on the label.** `scripts/check-linear-sync.sh` reconciles the
backlog's declared tier against the Linear **`priority` field** (reads `n.get("priority")`, maps `{2:HIGH, 3:MEDIUM,
4:LOW}`), and **never reads the `High`/`Medium`/`Low` labels.** It already encodes **`docs/backlog.md` as the tier SoT**
(the Gold standard) and flags the *field* when it disagrees — its own header cites B134/B87 as the priority drift that
"slipped past the status-only guard twice." So retiring the labels breaks zero tooling.

**Decision — ADOPT the field as sole SoT; RETIRE the priority labels.** Priority lives in the native field, governed by
`docs/backlog.md`. Done 2026-09-22: retired `High` / `Medium` / `Low` / legacy `Maturity` via `retire_issue_label`
(reversible with `restore_issue_label`; retired labels can't be applied to new issues but stay visible on the terminal
items that already carry them). No field-backfill was needed — the open queue was already correct, and terminal items'
priority is history.

**Left undone, deliberately:** the ~150 `Done`/`Canceled` items keep their historical priority label (churning them to
strip a harmless, frozen label is the over-engineering the lab avoids). **Optional cosmetic follow-on:** strip the
redundant (but *agreeing*) priority label off the ~57 open items so the working board is field-only — ~57 reversible
writes, pure tidiness.

**This also settles the Labels feature's core question.** Labels were conflating two shapes: a field-shaped concept
(priority → moved to the field) and genuine facets (type: `Tech Debt`/`Bug`/`Feature`/`Improvement`/`Spike`; plus the
new operational `parked:*`). After this pass, labels are a **pure facet space** and priority is a field — the
state-vs-facet rule applied consistently across the whole workspace. Remaining label ideas to *spend* the freed space
(a `spike`/research flag, a domain/pillar tag) are open, low-priority options, not commitments.

## Projects / Initiatives / Milestones

**Real data (live, 2026-09-22).** **5 projects:** `Weyland Lab` (Backlog — the homelab), `Stud.IO` (Backlog —
the separate product), `rogueone Hardware` (Backlog — host faults; EMA-186 lives here), `start.me Curator`
(Completed — B132), `Service Transformation` (Backlog; k8s/Java/Spring; **0 issues**; 7 seeded course-module
milestones at 0%). **Initiatives: 0.** **Milestones: only on `Service Transformation`.** Cycles: cycle 7 is
current (4 issues, all Stud.IO); weyland runs continuous.

**Projects — KEEP, already adopted correctly.** Projects are the one container the lab genuinely needs: the
**product separator** (`Weyland Lab` / `Stud.IO` / `rogueone Hardware`), and it is *guard-enforced* —
`check-linear-sync.sh` check B fails on any project-less open issue (how EMA-186 / EMA-172 were caught;
[[linear-status-source-of-truth]]). `start.me Curator` (Completed) shows the pattern working end to end: a
bounded effort grouped under a project and closed.

**Initiatives — DON'T ADOPT, and the emptiness is correct.** Initiatives sit *above* projects — they group
**multiple projects toward one themed goal**, a portfolio layer for an org running many projects against a
strategy. This is a solo lab with 2–3 products where **projects are already the top level**; an initiative
would be a container with nothing to contain. It is the "collaboration/scale feature that doesn't earn its
place" criterion from this doc's opening, applied to hierarchy depth.

**The container-hierarchy rule (the general principle).** Linear nests Initiative › Project › Milestone ›
Issue. A nesting level earns its keep only where there is real *fan-out* at that level — multiple children
that need grouping AND a decision made at the parent's granularity. The lab has fan-out at **Project→Issue**
(many issues per product) but **none** at Initiative→Project (2–3 projects, no themed super-goal) or
Project→Milestone (backlog B-numbers already sequence within a product). So the useful depth is exactly two
levels; the other two are empty scaffolding. Adopt the level where the fan-out is; skip the levels where it
is not.

**Milestones — skip.** The only milestones that exist are the dead-track course TOC. Real work is already
sequenced by the backlog's B-numbers and Linear **epics** (parent issues — e.g. UX Redesign epic EMA-153 with
its 8 sub-issues, the Module 1–5 epics). Milestones would duplicate that grouping with a second, weaker
mechanism; the backlog is the phase record.

**Cycles (adjacent) — appropriate light use.** `Stud.IO` (active product dev) runs a cadence (cycle 7, 4
issues); `weyland` (continuous ops/build) does not. That split is right — sprints fit product delivery, not a
homelab's rolling backlog. Cycles get their own verdict later in the walk; current usage is sound.

**`Service Transformation` — retained by operator directive (do NOT archive).** I flagged its 0-issue /
seeded-milestone state as clutter and proposed archiving it; the operator vetoed emphatically. It is a
**planned track kept deliberately** (seeded, not yet populated), not dead scaffolding — recorded here so no
future pass re-proposes archiving it.

### Refinement (2026-09-23) — Projects mirror the active-repo set 1:1

**Operator decision:** every ACTIVE repo in `repos.yaml` gets a Linear Project, so the board mirrors the
active-repo set. This is the *scaffold-all* choice over my *lazy-align* lean — the operator wants the projects
present now, not created-on-first-issue. Executed 2026-09-23: created 4 empty projects for the previously
unmapped active repos — **`Algopedia` (P-EMA-6)**, **`emangini-tailwind-nextjs-contentlayer` (P-EMA-7)**,
**`freejack` (P-EMA-8)**, **`MyBodyGraph` (P-EMA-9)** — each in team EMA, lead Edward Mangini, with a GitHub
link resource. A live `list_issues` sweep confirmed those repos had **no misfiled work** (every hit merely
*mentioned* the repo name in a Weyland Lab issue), so the new projects are genuinely empty scaffolds.

**The model — `repos ⊆ projects`, not `repos = projects`.** Projects is a *superset*: `rogueone Hardware`
(P-EMA-4) is a legitimate project with no repo (physical-machine faults), and future cross-repo tracks will be
too. So the join is one-directional — every active repo has a project; not every project has a repo. A `stale`
repo (`midi_real_book`) gets no project until reactivated.

**The SoT is `repos.yaml`** — each active repo carries a `linear_project: "<Project Name>"` field. (I first
stored the `P-EMA-N` identifier for rename-stability, but discovered the raw Linear GraphQL API exposes only
`id`/`slugId`/`name` — `P-EMA-N` is an **MCP-only synthetic** the CI guard can't resolve — so the value is the
project **name**. A rename now fails the guard with a clear "update repos.yaml" message, which is correct
hygiene, not a flaw.) Map: weyland-lab→"Weyland Lab", stud.io→"Stud.IO", ServiceTransformation→"Service
Transformation", startme-curator→"start.me Curator", Algopedia→"Algopedia",
emangini-tailwind-nextjs-contentlayer→"emangini-tailwind-nextjs-contentlayer", freejack→"freejack",
MyBodyGraph→"MyBodyGraph".

**Guarded (2026-09-23).** `check-linear-sync.sh` gained **check G** — every active repo's `linear_project`
resolves against a live Linear **projects** query (not the issue snapshot: an empty project has no issues and
so never appears there). G1 flags an active repo with no `linear_project` (the onboarding gap); G2 flags a name
Linear no longer has. Fail-closed (zero projects / unreadable SoT = exit 2). 43 bats at the time (46 after B178's outage split), TDD Red→Green, live run
green (8/8 mapped). `onboard-repo.sh` prints the create-project step when a new repo is added. The `linear-sync`
CI step apk-adds `py3-yaml` for the `repos.yaml` parse.

## Reviews (code diffs in Linear)

**Real data (MCP `list_diffs`, 2026-09-22):** 15 diffs (~13 open), **100% dependabot dependency bumps** across 5
repos (weyland-lab, stud.io, emangini-tailwind-nextjs-contentlayer, midi_real_book, gearlist-in-stud.io), every one
`isReviewRequested` → the operator, all `currentDecision: pending`, most `needsAttention`. **`lastSubmittedDecision:
null` on every one — zero reviews have ever been submitted through Linear.** A couple carry `sourcery-ai` bot comments.

**The finding: Reviews is the *workbench* view of the exact population the Inbox only *points* at.** Same dependabot
PRs as the Inbox verdict — but richer: it carries `mergeStatus` (ready/blocked/behind), diff stats, review threads
(`get_diff_threads`), and it can approve/comment in-app (`submit_diff_review`). Where the Inbox is a bare event
pointer, Reviews is a fuller mirror plus an action surface.

**But the trust ceiling is identical, and the data proves it.** `mergeStatus: "ready"` means *mergeable*, not *safe*.
#72 (soupsieve) and #63 (aiohttp) both showed `"ready"` — yet those are the exact PRs `check-pr-lifecycle.sh`
classified **STALE / regressive** (#63 would silently downgrade `cryptography` 50→48, re-opening a CVE). Approving
from Linear's "ready" alone walks straight into the silent-downgrade trap. Reviews has *more* signal than the Inbox
but still **no currency/quality judgment** — "ready to merge" is not "correct to merge."

**Verdict — ADOPT as a low-trust cross-repo triage QUEUE; do NOT make it the decision surface.**
- **Value:** one place to *see* every open PR needing attention across all repos — genuine consolidation for a solo
  operator, and better than the Inbox for triage (state + diffstat inline). Rides **free** on the GitHub↔Linear
  connection already kept for the Inbox.
- **Ceiling:** the mechanical `check-pr-lifecycle.sh` stays the source of truth for PR *actionability*
  (STALE/SUPERSEDED/MERGEABLE/NEEDS-HUMAN); **nothing is approved or merged on Linear's review signal alone**. The
  reconciler resolves, Linear displays, GitHub is the state SoT.
- **Reality check:** 0 reviews ever submitted via Linear → don't force it into the workflow as an approval tool. It
  is a queue you glance at, not a gate you operate.

**The loop closed (B176, 2026-09-23).** When this verdict was reached, the reconciler that backs the queue's
actionability covered only weyland-lab, while the queue aggregated 5 repos. **B176** extended the reconciler to
*every* pr-lane repo in `repos.yaml` — so the queue and its mechanical resolver are now the same scope, and the
fleet's stale/superseded PRs were resolved (advisory + `--apply` verified across all 8). The Reviews queue is a
trustworthy *view* precisely because the source it mirrors is kept clean by construction — the "keep the source
clean so any mirror is trustworthy" principle from the Inbox verdict, now applied fleet-wide.

**Net:** Reviews and the Inbox are the same population, two views — pointer vs. workbench — and both get the same
treatment: a low-trust surface, with the mechanical reconciler as the truth.

## Agent (coding sessions) + Skills

**Real data (MCP `list_agent_skills` + Linear docs, 2026-09-22):** **zero agent skills exist.** The "Agent" is
Linear's **coding-sessions** feature — delegating an issue to `@linear` starts a coding session in a **managed
cloud sandbox** (Claude Code or Codex), which drafts a PR and drops the diff in the Reviews tab. Usage **draws
from AI credits** ($20/user promo, then paid top-up); supported on Basic/Business/Enterprise.

**Verdict — DON'T ADOPT the Agent as a coding surface.** It fails both hard constraints: it runs in **Linear's
cloud, not the LAN**, and it **costs AI credits, not $0**. And it **duplicates** what the lab already does for
free — local Claude Code (this very evaluation runs in it) does agentic coding on the repos, on the LAN, at $0. A
cloud, paid agent buys nothing the lab lacks. Same rejection logic as initiatives: a feature assuming budget/scale
the lab doesn't have.

**But the Skills concept is real, portable, and worth investing in — separately from the paid Agent.** Linear-agent
skills aren't a proprietary Linear store; the docs are explicit that sessions use **repo files** — a `skills.md`
and "the existing Claude Code or Codex setup your team already uses." So a skill is a **portable artifact with a
swappable consumer**: the same file feeds local Claude Code (LAN, $0) and *would* feed the Linear cloud agent if
ever paid. The lab already has the registry: **`register_bifrost_skills.py`** (a git-versioned `SKILLS` list) is
the SoT, and Bifrost **serves the skills as a Claude Code / Codex plugin marketplace**
(`/api/skills/serve/claude-code/...`), so they install straight into the coding agents.

**Shipped 2026-09-23 — 4 loop-skills seeded (executes B175).** The existing ~21 skills codify runbooks/gotchas
("how to do X"); the four new ones are **loop-shaped** — the forwardfuture loop-library shape, with explicit
**checkpoints + a terminal condition** that stops the loop: `dod-8-pillar-gate`, `master-the-tool-walk`,
`pr-lifecycle-reconcile`, `full-guard-suite-preship`. Authored into the git SoT (syntax-verified, idempotent, 25
skills total); they register to Bifrost on the next `dagster-user-code` redeploy (or the weekly
`bifrost_skills_registered` asset), then serve to Claude Code via the marketplace. This answers B175's open
"Bifrost-SoT vs docs-catalog" question — **Bifrost-SoT** — and seeds the library with the lab's real loops.

**Net:** the Agent is a paid cloud duplicate of local Claude Code (skip); the Skills are a $0, LAN-native, portable
investment (done — seeded B175's loop library in the Bifrost registry, consumable by local Claude Code today).

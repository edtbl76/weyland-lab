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
| **Projects / Initiatives / Milestones** | **Projects: KEEP (already core, guard-enforced). Initiatives: ADOPTED 2026-09-24 (revisited — was DON'T ADOPT; see § Initiatives (revisited)). Milestones: skip.** | Projects are the product separator (`Weyland Lab` / `Stud.IO` / `rogueone Hardware`), enforced by `check-linear-sync` check B (no project-less open issue). **Initiatives** (0 defined) sit *above* projects to group many projects toward a themed goal — nothing for that layer to organize at a solo 2–3-product scale; projects are already the top level, so an initiative would be empty ceremony. **Milestones** exist only on the `Service Transformation` project (as a course TOC); real work is sequenced by backlog B-numbers + Linear **epics** (parent issues), so milestones would duplicate that with a weaker mechanism. Container-hierarchy rule: adopt the nesting level with real fan-out (Project→Issue), skip levels without it (Initiative→Project, Project→Milestone). `Service Transformation` (0 issues, seeded milestones) is a **planned track the operator keeps — explicitly NOT to be archived.** |
| **Reviews (code diffs)** | **ADOPT as a low-trust cross-repo triage QUEUE — NOT the decision surface** | Linear's Reviews is the *workbench* view of the same population the Inbox only *points* at: the fleet's open dependabot PRs (100% of the 15 diffs pulled, across 5 repos), all requesting review, **zero ever reviewed in Linear**. Richer than the Inbox (`mergeStatus`, diff stats, threads, in-app approve) but the **same trust ceiling** — `mergeStatus: "ready"` means *mergeable*, not *safe*: #72/#63 read `ready` while `check-pr-lifecycle.sh` classified them STALE/regressive (#63 = a silent cryptography downgrade). Keep it as a cross-repo triage queue (real consolidation, free on the GitHub↔Linear connection), but the **mechanical reconciler stays the SoT for PR actionability** — nothing merged/approved on Linear's review signal alone. As of B176 that reconciler covers *every* repo the queue aggregates, so view and resolver are finally the same scope. Same discipline as the Inbox (verdict #1). |
| **Agent (coding sessions) + Skills** | **DON'T ADOPT the Agent (paid cloud, duplicates local Claude Code); DO invest in portable skills (git SoT + Bifrost registry)** | Linear's "Agent" = **coding sessions**: delegate an issue → Linear spins a coding session in its **managed cloud sandbox** (Claude Code/Codex), drafts a PR. It **costs AI credits** (not $0) and **runs in the cloud, not the LAN** — duplicating the local Claude Code workflow the lab already runs free. Fails both hard constraints → don't adopt. **Covers the self-hosted variants too (2026-09-25):** e.g. **Cyrus** (Apache-2.0, runs Claude Code on your own machine, BYOK) fixes cost + cloud but is still *delegate an issue → coding session → PR* — the duplication of the local Claude Code workflow stands, and it adds a new cost: Linear's webhooks would need an ingress into the LAN. Same for the rest of Linear's agent directory (Codex, Cursor cloud agents, Copilot agent, Factory, Devin, Charlie, …); **cto.new** is genuinely free (frontier models, no keys) but fails on cloud (clones repos, incl. private, into its VMs) + duplication. **Integrations-directory sweep, 2026-09-25 — 12 more, all DON'T ADOPT, researched with sources:** *cloud agent → PR (the rejected pattern):* Tembo, [code]smith (free ended 2026-08-15), Blocks (free 250 min/mo + BYO keys; 7 of 9 repos are public so exposure is limited — but it is the rejected pattern, UNATTENDED; kept as a **comparator in B179** — Warp vs Blocks, what a "software factory" gives a solo lab that interactive Claude Code doesn't), TierZero (incident agent, paid, acquired by Cognition), Stilla (meeting agent + PR drafts; being acquired by Meta); *duplicates a self-hosted system:* Reflag (hosted flags, JS/TS-first + Ruby, others via HTTP API/OpenFeature — a cloud copy of the self-hosted Unleash, which is language-agnostic), Dash0 (hosted OTel — have Prometheus/Loki/Tempo/Pyroscope/Grafana + the Grafana MCP), Larridin (enterprise dev analytics — have Port + SonarQube + LiteLLM/Bifrost cost); *needs something the lab doesn't use:* Sanity Content Agent (a Sanity CMS), Minds (a research audience), Ranger (cloud-browser QA can't reach LAN apps); CellCog (one-time credits; duplicates the local LLM + Bifrost). Only Reflag and Sanity have a real $0 plan — both fail on fit, not cost. **Sweep continued (same day) — 6 more, all DON'T ADOPT:** *cloud agent → PR:* Sinatra (real free tier: 5 tasks/day on your own model key — still the rejected pattern), Replicas (paid, $50/mo); *duplicates a self-hosted system:* Solo (enterprise codebase Q&A from $750/mo — have Sourcebot + Zoekt + graphify + `context_ask`), Testifly (AI E2E tests; the Linear integration needs its $89/mo tier and it can't reach `*.weyland.lab` for free — have Playwright MCP + Claude Code, Keploy for APIs); *built for teams/business functions the lab doesn't have:* Coco by Cotera (sales/ops agents, one-time credits), Jellyfish Agent (DevEx survey on every closed issue — no team to survey). **Third sweep (same day) — 15 more, all DON'T ADOPT:** *cloud agent → PR:* Jules MCP (Google; real free tier, 15 tasks/24h — free doesn't fix the pattern, same as cto.new), Producta (1-month trial only), Tusk (unit tests as PRs; Linear on the paid Team plan), Builder.io MCP (Fusion visual agent → UI PRs; free 60 credits/mo; overlaps Figma Make + the Figma MCP, B39); *duplicates what the lab already runs:* CleanSlate (agents over Linear issues = Claude Code + the Linear MCP), Postman Agent Mode (files issues via the Linear MCP; Keploy covers API tests), 11.ai (ElevenLabs voice assistant, free in alpha, cloud — the operator's Telegram lane covers chat-ops), Alkemi (team reporting — views + Port), APX (Datadog/Postgres agents — no Datadog; Prometheus alerting + the Postgres MCP), Lovable MCP (Figma Make on the existing Figma Pro is the prototyping path, B181), Qodo (PR vs issue-requirements compliance — Qodo was cancelled in B106; its OSS PR-Agent already runs via the gateway); *needs what the lab doesn't have:* Fellow, Spellar AI (meeting capture — no meetings; Fellow's Linear link is paid-only), Attio Agents (a CRM). **CodeRabbit** is the near-miss: it is ALREADY adopted (B106, free public-repo tier), and its Linear integration (PR checked against the issue's acceptance criteria, coding plans, issue creation) is useful — but CodeRabbit's docs gate it to Essentials and above, excluding Free/OSS, so it stays unconnected. **Fourth sweep (same day) — 14 more, 1 ADOPTED:** **Codex MCP — ADOPTED** (config, not a product: Codex CLI → Linear's hosted MCP, OAuth; `codex exec` verified `linear/get_issue` on EMA-239; setup in `docs/runbooks/coding-agents.md`, which also records the Ubuntu 24.04 bubblewrap/AppArmor fix Codex's sandbox needed). DON'T ADOPT: *MCP-client entries for editors the lab doesn't use:* Zed, Notion Custom Agents (no Notion; Business plan); *duplicates what the lab already runs:* ContextStream (hosted agent memory; re-judged 2026-09-25 after "cloud is fine if free": the free tier is real — 10k credits/mo, 15 projects — but per-operation credit cost is unpublished and it would be a second, proprietary memory store. The need it names is real, though: **shared memory across harnesses** is now **B182** (EMA-240), candidate = an MCP memory server behind Bifrost), Gemini Enterprise (paid; Claude + the Linear MCP), Super (team Q&A over Linear), Systemprompt.io (MCP management from mobile — Bifrost manages MCP servers, the operator's Telegram lane is the mobile path; also judged vapor on inspection 2026-09-25 — interesting idea, no usable product yet, revisit only if it ships), Lovable (prototyping path already decided, B181); *paid or built for teams/functions the lab doesn't have:* Graph (team insights; its agents need paid Slack), Kraftful (customer feedback), Reclaim.ai (Linear is paid-only, not on Lite), Rize (paid time tracking), Hookshot Proteges ($99/mo+). **Warp** is not judged here — it is B179's own subject, with Blocks as its comparator. **Figma Make — ADOPTED (2026-09-25):** Linear's verified MCP connector inside Figma Make's chat — reads issues/projects/documents into a Make session and creates/updates issues back; $0 extra on the existing Figma Pro plan (Make needs a Full seat on a paid plan; connectors are on all plans), but connector context counts toward Make's 3,000 AI credits/mo, so pull the specific issue, not a project. Enabled together with the GitHub connector. It also supersedes the Figma Make half of B181 (a URL launcher): Make fetches the issue itself. Evaluating Make's Connectors / Designs / Skills properly is **B183** (EMA-241). **VS Code MCP — ADOPTED (2026-09-25, reversing the earlier DON'T at the owner's call):** VS Code reaches Linear through the **Codex extension** (`openai.chatgpt`, which uses `~/.codex/config.toml` — Linear + Bifrost already wired), with the Claude Code extension (`anthropic.claude-code`) installed beside it; the native `linear` entry in `~/.config/Code/User/mcp.json` (`code --add-mcp …`) serves Copilot Chat only. Editors are hosts, not harnesses — see `concepts/multi-harness.md`. **Also 2026-09-25:** Gemini Enterprise (paid-only product; the lab's free Gemini is a different thing) and Reclaim.ai (Linear is paid-only, not on Lite) confirmed DON'T; **PagerDuty — DON'T** (not used; alerting is Alertmanager → Telegram); **Sentry — DEFERRED to B53** (the Sentry ↔ Linear integration is folded into the B53 Sentry spike, where it is weighed against GlitchTip). **Linear Connect (VS Code) — DON'T (installed, tried, uninstalled same day):** Linear's official VS Code extension (`linear.linear-connect`) is only an authentication provider — no UI of its own; it lends a Linear sign-in to other VS Code extensions, and none installed use it (Codex and Claude Code reach Linear through their own MCP configs). Side items spun out of the walk: B183 (Figma Make), B184 (Slack), B185 (time tracking), B186 (GitLens). **incident.io — DON'T (deferred to B184):** the free Basic plan is real (Slack-native incidents, 1 schedule, 1 status page, 1 workflow, 2 integrations) but everything that would actually be used — API/webhooks, MCP, AI summaries/root cause, multiple schedules, private incidents — is paid; free self-hosted alternatives (Keep, OneUptime) and the Telegram ↔ Slack routing split are now part of B184's audit. **Honeybadger — DON'T:** bundles error tracking (free 5k/mo, 15-day retention), logs (50 MB/day), uptime (1 monitor), cron check-ins and a status page — each already self-hosted here (GlitchTip, Loki, blackbox + Uptime Kuma, the hand-rolled cron-freshness guards, Kuma's status page); free-tier integrations are GitHub/Slack/email only, and the commercial-vs-GlitchTip comparison slot is already B53 (Sentry). **Retool — DON'T:** a real free plan (5 users, unlimited apps, 500 workflow runs/mo; self-hosting NOT on Free) and its Linear resource can create/report/update issues — but a cloud-hosted builder cannot reach the LAN-only `*.weyland.lab` services, so it could only join SaaS APIs (Linear/GitHub/Port), and Port already is the lab's self-service UI + actions layer; no concrete internal app is waiting on a builder (if one appears, a self-hosted builder such as Appsmith/ToolJet is the lab-native evaluation). **Aldena — DON'T:** an AI-agent platform (agents in "rooms" read/update Linear and do the engineering work) — the rejected cloud-agent pattern, and only a 14-day trial with a card, no free tier. **Sweep continued (2026-09-25) — 6 more, all DON'T:** All Quiet (incident management with Alertmanager + Slack + Linear integrations, but plans start at $4.99/user/mo — no forever-free tier; the free incident candidates are Keep / OneUptime in B184), GitHub Enterprise Cloud (paid GitHub tier; the free GitHub ↔ Linear integration is already connected), Iteration X (browser bug capture, Jira-first; the lab has no outside users filing bugs), Marker.io (website feedback/bug reports; 15-day trial only), Merge (a unified API for SaaS vendors building integrations into their own product — not a lab use), Neat (free Linear/GitHub notifications app, but macOS-only — no Linux build). **Sweep continued — 5 more, all DON'T (Qodo re-listed, already judged):** Netlify (the lab hosts nothing on Netlify — apps are LAN services), **PostHog** (free cloud tier, creates/links Linear issues from analytics/replays/errors — no product analytics exist here, but nothing needs them yet; deferred as **B188** (LOW, `parked:held` on OJay Floyd / MyBodyGraph having real users), together with Iteration X / Marker.io-style feedback capture), Testmo (paid test management; tests are code in CI), Truto (a unified API for SaaS vendors, like Merge), Warestack (GitHub events as Linear comments — the connected GitHub ↔ Linear integration already links PRs/commits). **Sweep continued — 9 more:** DON'T: Delvyn Studio (AI spec writing — AI-DLC + the backlog), Deviera (CI failures / stale PRs → issues — `check-pr-lifecycle.sh` + CI alerting), Trigger.dev (Apache-2.0 background jobs — a fourth scheduler beside Dagster / CronJobs / Woodpecker), Spike (one free month, then paid), Testsigma (paid AI test generation), Testomat (free for 2 users / 2 projects, but tests are code in CI), groundcover (free forever but 12-hour retention in your own cloud account; duplicates the LGTM + Pyroscope stack), Todo comments for Linear (a paid VS Code extension). **Runframe — candidate for B184** (hosted incident response free for up to 5 users: on-call, escalation, status page, AI post-incident reviews, Linear follow-ups — the hosted, zero-RAM counterpart to the self-hosted Keep / OneUptime). **Sweep continued — 8 more, all DON'T (CodeRabbit re-listed, already judged):** *coordination between people:* Axolo (a Slack channel per PR synced to its Linear issue — now a B184 audit candidate), Livecycle (PR reviews + preview environments → Linear), Opsgenie Triage (Opsgenie not used), Pagerly (Slack triage rotations, $19/team/mo). **Correction (owner, same day):** rotation was first dismissed as meaningless for one person — wrong: the lab should RUN and TEST on-call, so **B184 now requires at least one exercised pager rotation** (e.g. between two Telegram channels), provided by the chosen incident tool (OneUptime / Runframe schedules) rather than a paid rotation add-on; *already covered:* GitHub Enterprise Server (regular GitHub + the connected GitHub ↔ Linear integration), Kualitee (paid test management — the question is now B189), Pensar (AI security findings → Linear — the scan suite + SonarQube + Trivy are the DoD Pillar 7 lane); *needs users:* Modem (customer feedback → issues — joins the B188 held stack). **Sweep continued — 10 more:** **Testiny → B189 candidate** (hosted test management, free for up to 3 users, Linear integration on the free plan — the only hosted free test tool with a Linear link). **SpecBot — ADOPTED (tried same day):** scores a Linear issue's readiness for an AI coding agent on 8 dimensions (objective, expected behavior, acceptance criteria, edge cases, technical context, dependencies, repro, priority/scope), threshold 80; free 25 analyses/mo; invoked by mentioning `@SpecBot` in the issue (`recheck` after fixes). First run: **EMA-240 (B182) scored 51/100 — NOT READY** (acceptance criteria 12, edge cases 10, priority/scope 12). The gap was systemic (every AI-drafted issue used Why/Scope only), so it was fixed at the source: the Backlog item / Spike / Bug templates gained Acceptance criteria + Edge cases + Out of scope sections, and `AGENTS.md` now requires them of every harness. A self-hosted replacement is **B190**. DON'T: Runway (mobile release management — no mobile apps), Shake (in-app bug reports — needs users; B188 stack), Spades (team planning-poker estimation), Rootly (incident management, $20/user/mo — the free incident candidates are in B184), AppDeploy (publish web apps from Linear — unverified; overlaps Figma Make / B183), TestOrchestrator (test cases from Linear — B189 covers test management), Graphite (stacked PRs; you commit to main, and GitHub is the PR surface), Highlight (session replay + errors — needs users; B188 stack; its status after the LaunchDarkly acquisition is unverified). **Tally: 94 directory integrations checked, 4 adopted (Codex MCP, Figma Make, VS Code MCP, SpecBot); the only live evaluation thread is B179.** BUT its "skills" are just **repo files** (`skills.md` / Claude Code skills), which the lab already owns: `register_bifrost_skills.py` is the git SoT, and Bifrost **serves them as a Claude Code marketplace**. So a skill is a portable artifact with a swappable consumer — invest there ($0, LAN, local Claude Code now; the Linear Agent later if ever paid). Seeded 4 loop-skills (DoD gate, master-the-tool walk, pr-lifecycle reconcile, full-guard-suite) — executes B175. |
| **Views (custom views)** | **ADOPT — 19 workspace views (10 question views + a High × open-project set), each answering a recurring question no other surface answers** | Views are free, native, and shared. The bar: a view must answer a question this workspace actually asks, better than any existing surface. Ten clear it (In flight · Parked · Tier spread · Shipped this week · Opened recently, still open · Blocking chains · Hygiene tripwire · Tech Debt · Stale backlog · Repo portfolio). Skipped: per-product (project pages), by-state (66/70 open are Backlog), by-assignee (solo, 0 assigned), cycle (built in), and any "what's next" ranking (`backlog.md` order is the SoT; Linear priority is only the tier). Created via the GraphQL API 2026-09-24, every one verified against a live count. **Scope: WORKSPACE, not team (2026-09-25).** One team (EMA), many initiatives — and it stays one team even with family members added. A team-scoped view appears ONLY on the team's Views page (tried with *In flight*, reverted), so views stay workspace-level. The High × project set is rebuilt idempotently by `scripts/linear-high-project-views.py` (onboard-repo.sh prints the step) — `High · OJay Floyd` was missing until 2026-09-25 because the script lived in a scratch dir. |
| **Team Home (Overview / Team resources / Documents)** | **ADOPT MINIMAL — a one-line description + resource links in one section PER INITIATIVE (as built 2026-09-25); DON'T ADOPT Linear Documents** | Home is the team's landing page. It earns a place only as a *pointer* to where truth lives outside Linear: **Docs** (`https://docs.weyland.lab` — `mkdocs-site.yml` builds all of `docs/`, so the backlog, DoD, runbooks and demos are already there), **Port** (`https://app.port.io` — the IDP), **Bifrost** (`https://bifrost.weyland.lab` — the AI gateway + MCP/prompt/skill registry). Description: *"Status lives here. Order and detail live in git: docs.weyland.lab (backlog, DoD, runbooks)."* — the `check-linear-sync` rule in plain words. **As built:** sections mirror the 6 initiatives — Lab & Systems (Docs, Port, Bifrost, GitHub weyland-lab) · Music Studio (stud.io repo) · Helper Tools (OJayFloyd, startme-curator repos) · Learning (freejack) · My Work (emangini.com + Vercel, Algopedia, ServiceTransformation, blog repos) · Health and Fitness (MyBodyGraph) — so Home is the portfolio's launchpad, grouped the same way the initiatives drive scope. **Documents: DON'T ADOPT** — authoring docs in Linear would fork the git record (guarded by the doc checks) into an unguarded copy. **Views not linked** — the 19 views are one click away in the sidebar. Set in the UI: team resources are `TeamPinnedResource` and the API has **no pin mutation** — `entityExternalLinkCreate(teamId)` succeeds but makes an UNPINNED, invisible link with no list query to find it again (3 such orphans were created trying, 2026-09-25). The description WAS set via `teamUpdate`. |
| **Labels — issue + project** | **ADOPT a single-select `Kind` group (Bug · Feature · Improvement · Tech Debt · Spike); keep `parked:*`; DON'T ADOPT project labels** (2026-09-25) | Before: 41 of 72 open issues (57%) carried no kind, Spike/Improvement were never used (not even on the 4 open *Investigate* items), nothing enforced one-kind-per-issue, and Tech Debt/Spike were team-scoped while the rest were workspace-scoped. Now: a workspace `Kind` label **group** (`singleSelect` — Linear enforces exactly one), Spike applied to the investigations (B179/B174/B161/B86), a reviewed 36-issue backfill → **71/72 open issues carry exactly one kind, none two**. Definitions: Feature = new capability · Improvement = better existing capability/process · Tech Debt = paying down built-but-messy/deferred/unsafe · Bug = broken · Spike = investigation whose output is a verdict. `Maturity` (retired, **0** uses ever) deleted; retired High/Medium/Low stay as history on 143 closed issues. **API limit:** a label's team/workspace scope can't be changed via API (`IssueLabelUpdateInput` has no `teamId`) and a team label can't sit under a workspace group (`parent label team mismatch`) — Tech Debt/Spike were moved to workspace in the UI (Team settings → Labels), then joined `Kind` (done 2026-09-25). **Gotcha:** the UI "move to workspace" REPLACES the label (new id; issues carried over — Spike 9, Tech Debt 24 verified), so any view filtering on a label **id** would silently empty; ours filter on label **name** (*Tech Debt*, *Parked*) and were re-verified (Tech Debt view 16 = 16 open). `parked:held`/`parked:deferred` stay prefixed labels (the *Parked* view filters on `parked:`). **Project labels: don't adopt** — initiatives group projects, project status carries lifecycle, `repos.yaml` holds repo facts; a label would be a drifting copy. |
| **Issue templates** | **ADOPT — 4 workspace templates: Backlog item (default) · Spike · Bug · Bucket** (2026-09-25) | Answers B119's original evidence item *"nothing enforces fields at creation"* (EMA-190 sat 11 days with no B-number and no backlog row). Linear templates **pre-fill** but cannot make a field **required** — so templates are the PREVENTION and `check-linear-sync` stays the ENFORCEMENT (it fails on a missing B-number, backlog entry or project). Each pre-fills a `B<n> — ` title + a description skeleton ending in the backlog-entry reminder: **Backlog item** (Why · Scope · Done when) · **Spike** (Kind=Spike; Questions · Constraint gate $0/self-hosted/LAN · Overlap · Deliverable = verdict in `docs/concepts/`) · **Bug** (Kind=Bug; Observed · Expected · Repro · Evidence · Fix + regression test) · **Bucket** (umbrella over sub-issues — no Kind, children carry kinds; Purpose · Scope · Children · Exit criteria · parent priority = floor for children). **Project and Priority are deliberately NOT defaulted** — a default project mis-files cross-product work silently; a missing one is caught by check-linear-sync, a missing priority by the *Hygiene tripwire* view. Created via `templateCreate` (markdown `description` → stored as `descriptionData`). Setting *Backlog item* as the team's default template is UI-only (Team settings → Templates). |
| **Project statuses + project templates** | **Statuses: KEEP the 5 defaults, but SET them (2026-09-25). Project templates: DEFER to B159.** | Before: 9 of 10 live projects sat in `Backlog` — incl. Weyland Lab (173 issues, worked daily) and Stud.IO (40 open) — so status carried no signal and the *Repo portfolio* view (grouped by status) was one bucket. Meanings now: **In Progress** = active work (Weyland Lab, Stud.IO) · **Planned** = committed next, not started (OJay Floyd, MyBodyGraph) · **Backlog** = idea/scaffold/dormant (Algopedia, blog, freejack, Service Transformation, rogueone Hardware — its one issue is `parked:held`, so the label carries the blocked state; no custom `Paused` status) · **Completed/Canceled** = finished/dropped (start.me Curator). **Project templates deferred to B159:** projects are rare, scripted, and of several types (repo / hardware / track / application); a template that COPIES onboarding steps drifts from `onboard-repo.sh`, so the onboarding service will create each type from a pointer-only template (scope add recorded on B159/EMA-216). |

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

**Initiatives — DON'T ADOPT (2026-09-22; SUPERSEDED 2026-09-24, see § Initiatives (revisited) below).** Initiatives sit *above* projects — they group
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

### Initiatives (revisited, 2026-09-24) — ADOPTED, and they drive the guard's scope

**What changed is the evidence, not the rule.** The container-hierarchy rule above still holds — adopt a level
where there is real fan-out. On 2026-09-22 there were 2–3 live projects; after the scaffold-all decision
(every active repo maps 1:1 to a project, 2026-09-23) plus OJay Floyd there are **10**, spanning unrelated
domains. That is fan-out at Initiative→Project, so the level now earns its place.

**The map (operator-chosen, project by project):**

| Initiative | Projects |
|---|---|
| **Lab & Systems** | Weyland Lab, rogueone Hardware |
| **Music Studio** | Stud.IO |
| **Helper Tools** | start.me Curator, OJay Floyd |
| **Learning** | freejack |
| **My Work** | Service Transformation, Algopedia, emangini-tailwind-nextjs-contentlayer |
| **Health and Fitness** | MyBodyGraph |

"Weyland is both an initiative and a project" resolved as: the **initiative is Lab & Systems** (the lab plus the
physical machines it runs on), the **project stays Weyland Lab**. OJay Floyd (financial-services app grounded in
accounting + economics; roadmap = an accounting text) was created with this pass — repo `edtbl76/OJayFloyd`
(public), project, Helper Tools, and onboarded in `repos.yaml` across every enforced lane.

**Why it is more than labelling: initiative membership IS the weyland scope.** `check-linear-sync.sh` checks E
(orphan) and F (unnumbered) apply only to issues whose work `docs/backlog.md` governs. That used to be a
hard-coded denylist of "other products" (`Stud.IO`, `start.me Curator`), which went stale the moment a new
project appeared — every new repo project was silently treated as weyland. Now the scope is **the projects of
the `Lab & Systems` initiative, read live** (`LINEAR_SCOPE_INITIATIVE`). Filing a project under that initiative
is the one act that puts it in scope; a missing or empty scope initiative is exit 2 (fail closed — "nothing
in scope" would check nothing and report OK).

**New check H** keeps the map honest: every live (non-canceled) project must sit in **exactly one** initiative
— in none, it is in no one's scope; in two, the scope is ambiguous. `scripts/onboard-repo.sh` prints the
initiative step alongside the project step.

**Plan note.** Workspace initiatives are available on this plan; *team* initiatives (`leadTeam`) require the
Business plan, so the six were created without a lead team.

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
Linear no longer has. Fail-closed (zero projects / unreadable SoT = exit 2). 43 bats, TDD Red→Green, live run
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


## Views (custom views)

**Real data (live GraphQL, 2026-09-24):** **0 custom views.** 70 open issues — Stud.IO 40 · Weyland Lab 29 · rogueone Hardware 1. **66 of 70 sit in Backlog** (3 In Progress, 1 Todo). **0 assigned** (solo), so the built-in *My issues* is permanently empty. Labels on open issues: Feature 16 · Tech Debt 13 · Bug 2 · `parked:held` 2 · `parked:deferred` 1. Tier spread: Stud.IO **18 H / 16 M / 6 L** (top-heavy), Weyland Lab 7 / 11 / 11. 3 issues in a cycle (Stud.IO only).

**Verdict — ADOPT, 10 views.** A first pass proposed only *Parked* ("a facet with no other surface"); the operator pushed back, rightly — the real bar is **a question this workspace actually asks, answered better than by any existing surface**. The adopted set (workspace-level, shared):

| View | Filter | Question it answers | Live count |
|---|---|---|---|
| **In flight** | state = started | "What am I working on?" — replaces the empty *My issues* | 3 |
| **Parked** | label starts with `parked:` | the surface for the parked facet (workflow-states verdict: parked is a label) | 3 (B134, B150, B86) |
| **Tier spread** | open; grouped priority × project | DoD Pillar 5 tier-rebalance input (priority FIELD is the SoT) | 70 |
| **Shipped this week** | completed in last 7d | weekly review / close-out evidence | 6 |
| **Opened recently, still open** | created < 14d, open | the dangling-record tripwire (create it → complete it) | 4 |
| **Blocking chains** | open; has blocking or blocked-by relation | dependencies gating other work | 2 (EMA-195 → EMA-218) |
| **Hygiene tripwire** | open; no project OR no priority | should always be empty — the UI mirror of `check-linear-sync` checks B/C | 0 |
| **Tech Debt** | label Tech Debt, open; grouped by project | batch debt triage | 13 |
| **Stale backlog** | open; untouched 60d+ | grooming candidates — *reads 0 until ~late Oct: the 2026-09-22 label strip touched every open issue* | 0 |
| **Repo portfolio** (Projects view) | all non-canceled projects; grouped by status | the repos ⊆ projects picture (which repos have work vs. empty scaffolds) | 9 |

**Not adopted:** per-product views (the 9 project pages are that), state views (66/70 Backlog — nothing to slice), assignee views (solo), cycle views (built in, Stud.IO-only), and any "what's next" ranking view — `backlog.md`'s ordered list is the SoT for sequencing and Linear's priority field carries only the tier, so a ranked view would be a second, drifting ordering.

**How they were built.** The Linear MCP can *list* custom views but not create them, so they were created with the GraphQL `customViewCreate` mutation (idempotent by name), and grouping via `viewPreferencesCreate` (organization-level; keys `issueGrouping` / `issueSubGrouping` / `viewOrdering` / `projectGrouping`, read back from `viewPreferencesValues` rather than guessed). Every view was verified by querying its issues/projects and matching an independent count.

**Findings along the way:**
- **One straggler from the priority-label migration:** EMA-101 (B108) still carried the retired `Low` label — one of the silently dropped MCP writes from the 61-issue strip. Removed; its priority *field* was already Low.
- **Blocking chains is 2, not the raw 3:** a naive scan counts EMA-111 and EMA-30, which "block" **EMA-46 — already completed**. Linear's `hasBlockingRelations` correctly ignores blocks on finished work, so the view is right; those two relations are stale and could be removed.
- **The local `LINEAR_API_KEY` has WRITE scope** (it created these views), while `check-linear-sync.sh` describes its token as read-scoped. The guard only needs read; least privilege says the CI secret `linear_api_key` should be a read-only key. **Done 2026-09-24:** `linear_api_key` now holds a read-only key (`LINEAR_API_KEY_RO`; writes return `FORBIDDEN`), green on CI pipeline 182; rotation command in `docs/runbooks/woodpecker.md`.

**Addendum (2026-09-24, operator request) — the "High × project" set.** One `High · <project>` view per **open** project
(8: Algopedia, emangini-tailwind-nextjs-contentlayer, freejack, MyBodyGraph, rogueone Hardware, Service Transformation,
Stud.IO, Weyland Lab) — open issues at priority High, filtered by **project ID** so a rename doesn't break the view — plus a
**`High — all projects`** index grouped by project. Every open project gets one (not just the two with High work today), so a
view fills itself in when work lands. **Closed projects get no view** (operator call): `start.me Curator` (Completed) had one
created and then deleted. Rule going forward: when a project completes, delete its `High ·` view; if it reopens, recreate it.
Verified against an independent count: Stud.IO 18 · Weyland Lab 7 · the other 6 empty · index 25. Workspace total: **19
custom views**.

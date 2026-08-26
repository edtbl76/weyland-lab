# Definition of Done

The weyland Definition of Done — the hard gate every body of work passes before it's "done." This page is the
**canonical, published** version (the RAG corpus + the shared reference); it supersedes any private note. A
capability is **NOT done** until ALL eight pillars hold. "Ran once" ≠ done.

> Added 2026-07-14; grown through B64 (render-verify), B69 (operational completeness), B111 (metrics-scrape
> ServiceMonitor + Grafana dashboard made explicit monitoring criteria), 2026-08-05 (tier rebalance at close-out —
> keep High/Medium/Low roughly equal), 2026-08-05 (B82 — one source of truth for a cross-surface taxonomy), and
> 2026-08-06 (B47 — the security / code-quality scan as a standing per-batch gate, Pillar 7), and 2026-08-23
> (B135 — **Pillar 8, cascading changes**: the DoD graded the thing built but never what it implied, so a new
> dataset could ship uncatalogued and a new timer undocumented without a single check going red).
> Applies retroactively and going forward.

## 1. Documentation sweep (every batch)

- **arch.md** — a **substantial** entry: comparative placement (why this vs the alternatives), a decision
  matrix/tradeoffs, and diagrams. Not a one-line entry — `arch.md` is a deliverable.
- **api.md + hosts.md** — updated for EVERY endpoint / host / IP / DNS / subdomain change.
- **schedules.md — the timer reconciliation check (every batch that adds/moves/removes a timer).** `docs/schedules.md`
  is the single source of truth for **every timer class** — Dagster schedules, DataHub managed ingestion, k8s
  CronJobs, node systemd timers, **and Woodpecker crons**. On any timer change, **reconcile the live timer against
  `schedules.md` in the same batch** — a timer that runs but has no row (or a row with no live timer) is **drift**,
  same failure mode as an unlisted host in `hosts.md`. The row must record the **NY-equivalent time, cadence, weight
  (heavy/light), and owner system**. Two hard constraints on every new/changed timer:
  - **Off-hours rule** — it runs ONLY in the pre-dawn window (~00:00–06:00 NY), **never mid-day**; the single node
    cannot absorb a scheduled job stacking on a manual/interactive load (2026-08-07 incident: a noon
    `timeseries`/`catalog`/`datahub_catalog_emit` cluster + a manual datasets-hydrate saturated mother, control
    plane unreachable). **Mid-day is manual-only.** (schedules.md Design Rule #5.)
  - **No heavy-on-heavy** — a new heavy timer must not share its slot with an existing heavy job; check the
    timetable for the nearest heavy neighbour before picking a time. **Clock caveat:** Woodpecker crons run in **UTC**
    (not NY-pinnable) — pick the UTC expression so the NY-equivalent stays off-hours in **both** EDT and EST.
- **Runbook** — `docs/runbooks/<x>.md` with the real operational commands.
- **Query cookbook** — `docs/query/<x>.md` if the workflow adds a queryable surface.
- **platform-map** — `docs/platform-map.html` (+ `docs/data-mesh-map.html`) refreshed for any component add / remove /
  rename / status change (the visual maps iframe'd by the **Platform Maps** nav section, `docs/platform-maps/`). They
  drift silently — a removed service leaves a ghost card.
- **Port catalog** — the Port.io catalog (blueprints + entities: `component` / `resource` / `k8s_workload`
  links, integrations) reflects the change. Port is the "see" layer; if it claims an integration/entity that
  isn't real (or misses one that is), that's **drift** — reconcile it, don't let it accumulate.
- **Relevance sweep — EVERY docs-site section, every batch** (not just the new page): check `runbooks/` ·
  `demos/` · `diagrams/` (C4 **and** `flow-*`) · `query/` · `concepts/` · `validation/` · `units/` · top-level
  (`arch`/`hosts`/`api`/`tools`/`schedules`/`README`/`platform-map`). Renaming/retiring one thing stales others.

## 2. Diagrams

- **Architecture (C4)** — the LikeC4 model (`docs/architecture/weyland.likec4`) updated to place the new
  component; explorer at `likec4.weyland.lab`, embedded in the C4 doc pages.
- **Sequence diagram** — every end-to-end workflow as a `docs/diagrams/flow-*.md` sequence diagram (real
  participants, ordered messages). An inline diagram in a demo does **not** satisfy this.

## 3. Demos — `docs/demos/` (exhaustive, not sampled) — AND the demo IS the test

- A demo per workflow, with **both** a **UI walkthrough** (real URLs) and a **CLI walkthrough** (real commands,
  host-labeled, no placeholders). `docs/demos/README.md` is the ledger.
- **UAT — eyes-on, where a UI is a valid deliverable.** When the workflow produces a **UI** (a dashboard, a catalog /
  data-product page, an IDP entity, a rendered view), the UI walkthrough MUST include explicit **UAT steps**: the exact
  places to click and what to **visually confirm** — it renders without error, shows the *right* data, and is in the
  expected state. A **human puts eyes on it.** The CLI test passing is necessary but **not sufficient** when a UI is
  the deliverable — a green pipeline can sit behind a blank or wrong dashboard. List UAT steps per UI surface.
- **The demo IS the validation** — it must be **RUN end-to-end against live infra**. There are no separate
  test-instruction files; the demo's CLI steps + expected output ARE the test. A demo written but not executed
  is **not done** (still MEDIUM, not DONE). This is the anti-fabrication guarantee.
- **Enforcement (per batch, at close-out):** audit every completed item against the `docs/demos/README.md` ledger
  **as part of the close-out** (same step as the Linear sync) — a new/changed capability with no ledger row, or a
  stale one, is **not done**. (This check is what surfaced the B70/B94 demo gaps on 2026-07-23.)

## 4. Cleanup / teardown

- Any demo that CREATES data ships a teardown that removes it. Read-only demos say so.

## 5. Close-out / tracking (the unit isn't done until the tracker says so)

- **Linear** — flip the tracked issue (`EMA-*`) to Done with a completion comment (what shipped, gotchas, links).
- **backlog.md** — flip the item to DONE with a substantial summary (backlog = ordered source; Linear = status).
- **Memory** — capture any durable, non-obvious lesson.
- **VERIFY IT — `bash scripts/check-linear-sync.sh`. Do not hand-tick this pillar.**

> ### Why this pillar has a checker now (added 2026-08-26, B148)
>
> Pillar 5 was **the only pillar with nothing that could contradict the person filling it in.** Every other
> pillar has one — `check-mermaid.sh`, `check-doc-counts.sh`, `check-cron-freshness-budgets.sh`, the bats
> suite, eyes on a UI. Here the tick *was* the work, so it recorded intent rather than outcome.
>
> It failed exactly that way on the day it was noticed: the **B148** close-out recorded
> *"5 — Linear EMA-207, backlog flipped"* while **no Linear call had been made at all**. The issue sat in
> `Backlog`. Checking then found **B143** had also been open for two days after shipping. Neither was
> visible from inside the checklist, because the checklist is where the claim was made.
>
> `scripts/check-linear-sync.sh` compares the two documents that make claims about each other:
>
> - **A backlog entry marked DONE whose Linear issue is not terminal.** One-way on purpose — an issue
>   closed in Linear while the backlog entry is still open is a normal mid-flight state, not drift.
> - **An open Linear issue with no project.** This team runs two products (Weyland Lab, Stud.IO) and
>   project assignment is the only thing separating them, so a project-less issue is invisible to *both*
>   filtered views while still counting in the team total. Two High-priority weyland issues were hiding
>   there — one open since 2026-08-12 and absent from every "what's next" answer.
>
> Runs **blocking in CI** (`.woodpecker.yml` step `linear-sync`, secret `linear_api_key`, events
> cron+manual) *and* by hand at close-out. Locally it needs `LINEAR_API_KEY` in the gitignored
> `scripts/.env` (Linear → Settings → Security & access); a read-scoped key is sufficient.
> Exit **1** = drift; exit **2** = the guard could not run. A missing token must never read as a clean
> backlog. 20 bats cases; `--list` prints every reference and its verdict.
- **Tier rebalance — keep High / Medium / Low roughly equal. PROPOSE IT, NEVER APPLY IT UNILATERALLY (2026-08-23).**
  Completing work drains the **High** lane, so at close-out re-tier to refill it: promote the strongest
  **Medium → High**, then backfill **Low → Medium** (and, as the tail grows, close or promote stale **Low** items — a
  Low that never rises is a drop candidate). It's a pull system: High pulls from Medium, Medium pulls from Low.
  - **The rebalance is a DISCUSSION, and the human has final say.** Present the current spread, name the specific
    items proposed to move and *why each one*, and then **stop and ask**. Do not move a single item's priority
    before an explicit answer. Priority encodes what the human intends to work on next — that is theirs to set, and
    it is not recoverable from the backlog text, so a well-reasoned guess is still a guess.
  - **"No move" is a legitimate outcome and must be offered as one.** If the lanes are already within tolerance,
    say so and propose nothing; forcing a promotion to look diligent is exactly the box-checking this gate exists
    to prevent. Count *per project* as well as overall — one project's cluster of frontend work can make a shared
    High lane look healthy while another project's High is quietly empty.
  - Once decided, apply the move in **both** `backlog.md` (the HIGH/MEDIUM/LOW tag) and **Linear** (priority field + the
    `High`/`Medium`/`Low` label), in the **same** close-out step as the status flip — the two must never diverge.
  This keeps the roadmap from silently emptying High while Low accumulates. Judgment, not arithmetic: "roughly
  equal," re-derived from the current open set, not forced to exact counts.

## 6. Operational completeness (deployed capabilities must be DURABLE, not "runs once")

Grade every deployed capability against the 5 gap types (see [completeness-audit.md](completeness-audit.md)). ANY
open gap = not done:

- **Reproducible from git (GitOps)** — the workload + config rebuild from the repo: Argo-onboarded, image on
  `registry.weyland.lab` (no `:local` / `imagePullPolicy: Never`), no un-codified crontab / systemd / UI-only config.
- **Secrets restorable** — no imperative-only secret: SealedSecrets/ESO/SOPS, or a committed
  `<name>-secret.example.yaml` + `runbooks/secrets.md` index; bricking keys (e.g. lakeFS `AUTH_ENCRYPT_SECRET_KEY`)
  escrowed.
- **Monitored + alerted — the four signals (metrics, logs, traces, profiles) + alerts + synthetic, all required:**
  - **Metrics** — if the service exposes `/metrics`, ship a **ServiceMonitor** so Prometheus scrapes it (the
    retroactive gap: most pre-B65 services have none — audit `count(up) by (job)`), **plus** a **Grafana dashboard**
    for its metrics (or an explicit confirmation an existing one covers it — no active service without a dashboard).
  - **Logs** — the service's container/app logs reach **Loki** (Alloy collects cluster-wide by default) and are
    **queryable in Grafana**; confirm it, and prefer structured/JSON logs where the app supports it.
  - **Traces** — if the service sits in a **multi-hop** request path, it emits spans to **Tempo** (OTel) and they
    appear in Grafana. For a **single-hop** service (e.g. an egress gateway like Bifrost), request-level tracing
    exported **to metrics** — a tracing plugin → Prometheus (latency histograms + per-request cost/tokens/errors) —
    satisfies this; full distributed spans only earn their keep across hops. Note **N/A** if it's not in a traced path.
  - **Profiles** — if the service is a profiling target (Go / pprof, or SDK-instrumented), continuous profiles reach
    **Pyroscope** and appear in Grafana's **Profiles Drilldown**; note **N/A** for services that don't profile.
  - **Alerts** — a **PrometheusRule** with a **down/failure** alert (+ spend / error-rate where relevant, e.g.
    `bifrost_cost_total`) routed to Telegram; the alert path has a **dead-man's-switch** (Watchdog → external heartbeat, not `null`).
  - **Synthetic 1:1** — **blackbox is the synthetic source of record.** Every user-facing host in `hosts.md` has a
    **blackbox probe target** (`k8s/monitoring/blackbox-exporter.yaml`, kept alphabetical) — **1:1, no orphans**, a
    **git-vs-git diff** of that target list against `hosts.md` each batch (add an ingress → add its probe in the same
    change, at a **working path** not blindly root). Two documented carve-outs: **(a) on-demand** hosts (the excluded
    list in the blackbox config — Flink session cluster, GPU benches) and **(b) DNS aliases** that aren't HTTPS
    ingresses (e.g. `ollama.weyland.lab` → the LAN IP:11434). Kuma is **supplementary** (UI / status page / push-heartbeat monitors / the Port `uptime_monitor`
    blueprint), NOT the coverage-of-record — don't reconcile against Kuma's PVC state.
- **Backed up (if stateful)** — any PVC/DB/object store with non-reproducible data has a **tested** backup
  (CronJob + rotation); reproducible stores say so.
- **Triggered** — anything that must stay fresh has a schedule/sensor + a freshness signal, not manual-only.

## 7. Security & code-quality scan (every batch that touches code)

Scanners are a **gate**, not a dashboard to admire. Any batch that adds or changes **code, a Dockerfile, or a k8s
manifest** runs the relevant scan and **triages the result before "done":**

- **Run** the `code-scan-suite` (the multi-language 19-tool suite — see `quality-tools.yaml`, the registry source of
  truth; B120) on-demand with **`./scripts/run-scan-suite.sh`** (clears any prior adhoc job → launches from
  `cronjob/code-scan-suite` → waits → prints findings; raw form:
  `kubectl -n weyland create job scan-suite-adhoc --from=cronjob/code-scan-suite`) — and, for changes SonarQube covers,
  `sonar-scan`. Both feed Port `security_scan` / `code_quality` (the **Code Health** dashboard). It's also a weekly
  CronJob (B69); this pillar is the **per-batch** gate on top of that safety net, not a substitute for it.
- **Triage every NEW critical / high.** Most highs are phantom (see [[code-quality-scan-triage]]) — **fix** the real
  ones; **explicitly accept** the false/systemic ones with a *documented reason* in the right place: `.trivyignore`
  (Trivy / KSV — rule-id + why), `osv-scanner.toml` (dependency CVEs), or a **bare `# nosemgrep: <rule-id>`** (Semgrep —
  rule-id ONLY; prose after `nosemgrep:` suppresses nothing). Never leave a new high un-triaged, and never blanket-
  suppress to make a number green.
- **Re-scan after fixes** so Port reflects the true state — a `202` from the ingest URL is queue-acceptance, **not**
  proof of an entity. "Scanned once and ignored" is not done.
- **RBAC / SA hardening guard (B95).** Any change touching a `ServiceAccount`, `RoleBinding`, `ClusterRoleBinding`, or
  `automountServiceAccountToken` runs **`./scripts/check-sa-automount-collisions.sh`** — it fails if any binding grants
  permissions to a `default` ServiceAccount (the automount-off SA), the collision that silently broke lancedb-sync
  (2026-07-20). A workload that calls the k8s API gets a **dedicated** SA (automount on), never `default`. See
  `k8s/rbac-default-sa-noautomount.yaml`.
- **AI code-review lane (B106) — run it on the change, triage like the scanners.** The adopted $0 stack (7 tools;
  [runbooks/code-review-stack.md](runbooks/code-review-stack.md)) sits ON TOP of the scanners — LLM contextual review
  the SAST lane can't do. For a change on a **PR**: the cloud bots (**DeepSource · CodeRabbit · Sourcery · Greptile**)
  auto-review + **PR-Agent** via `./scripts/pr-agent-review.sh <pr-url>` (routed through the LiteLLM gateway) — confirm
  they ran and address the real findings. For **direct-to-main** work: run **CodeScene** on the changed files via its
  MCP (`code_health_review` / `pre_commit_code_health_safeguard`) and fix Code-Health regressions before done;
  **ProxyAI** covers in-IDE review during authoring. Triaged like the scanners — fix the real ones, document-accept noise.

Runbook: [runbooks/code-quality.md](runbooks/code-quality.md).

## 8. Cascading changes (what else must move because this moved?)

**A change is almost never local.** The other seven pillars grade the thing you built; this one grades
everything that thing *implies*. Answer it explicitly before "done" — and **"nothing cascades" is a valid
answer that must still be written down**, because an unasked question and a genuinely-empty answer look
identical in a commit.

This exists because the failure it catches is silent by construction: nothing errors, no test goes red, no
alert fires. The new thing works perfectly and the surfaces that should have learned about it simply never
did. That is how the catalog starts lying, how a dataset becomes invisible to governance, and how a doc
becomes confidently wrong.

### Trigger → cascade

| You added / changed | Then these must move too |
|---|---|
| **A dataset / table / mart** | **DataHub** — ingested, in a **domain**, tagged to a **data product**, glossary terms attached, **column lineage** resolving upstream (not just the table node); **dbt** — is it a source or a mart, does it need tests-as-assertions; **data-quality** — a Soda/GE check, or a written reason it has none; **BI** — a Lightdash/Superset/Cube surface, or a written reason nobody queries it; **query cookbook** — `docs/query/<store>.md` gains real, dataset-specific queries; **the storage grid** — `docs/data-domain-storage-grid.csv` says which domain lives where; **retention/backup** if it is not reproducible |
| **A deployed service** | `applications.yaml` registry entry (or an explicit `kind: plumbing` with a reason) → Port `component`; **Kuma monitor**; a `*Down` **PrometheusRule**; **ServiceMonitor + Grafana dashboard** if it exposes `/metrics`; logs reaching Loki; LikeC4 placement; `arch.md` §6 inventory row |
| **An endpoint / host / DNS name** | `api.md`, `hosts.md`, a **blackbox probe target at a working path** (1:1, no orphans), forward-auth or a written reason it is not gated, `/etc/hosts` for new subdomains |
| **A timer** (Dagster · DataHub · k8s CronJob · systemd · **Woodpecker cron**) | `schedules.md` row with NY-equivalent + cadence + weight + owner; the off-hours and no-heavy-on-heavy checks; **a freshness signal** — something that notices when it stops, not just when it fails |
| **An image** | `scripts/ci/images.tsv` (or a written exclusion); the ship loop's gates then cover it; a `readinessProbe` on whatever runs it, since the SMOKE gate makes that a shipping requirement |
| **A repo** | every lane in the coverage matrix — CI, Port integration selectors, PR-lifecycle `PR_REPOS`, code-review stack, scan-suite, `tofu/github/` |
| **A classification used on ≥2 surfaces** | the single registry (see the cross-cutting rule below) — never re-encode it per surface |
| **A retirement / rename** | **the reverse sweep** — this is the one most often skipped |

### The reverse sweep

Removals and renames cascade *harder* than additions, because nothing fails: **platform-map** ghost cards,
orphan blackbox probes, stale Port entities and `k8s_workload` links, dangling doc links, a `schedules.md`
row whose timer is gone, a registry key with no workload, a dashboard querying a metric nobody emits, an
alert on a series that no longer exists. Sweep for the *absence* you created, not just the presence.

### How to run it

Walk the trigger table for the change, write the cascade list into the design/plan doc, then close each
item or record why it does not apply. Grade it like the scanners: **an unanswered cascade is not done**, and
a cascade deliberately deferred gets a backlog item, not silence.

**Worked example (B135/B131, 2026-08-23):** adding one CronJob cascaded into `schedules.md` (its row), the
`pr-lifecycle` `applications.yaml` entry (two jobs now share that Argo app, so the reason text was stale), a
sealed secret plus the `seal-secrets.sh` allow-list plus the count in `secrets.md`, a runbook, `arch.md`
§6/§9/§10b, and the freshness rule — which turned out to be missing **the watchdog itself**. Running the
timer reconciliation the same batch also surfaced three *unrelated* backup CronJobs that had no row and were
silently running on the wrong clock. None of that was the feature; all of it was the feature's wake.

## Cross-cutting: verify the render, sweep for drift

A green build is **not** proof of done — **verify the actual rendered output** the user sees after each step,
page by page. And **re-audit prior pages for drift** after each step: moving/renaming/retiring things silently
stales docs, diagrams, the platform-map, and the Port catalog. Sweep every time; don't assume earlier-verified
surfaces are still correct.

## Cross-cutting: naming & structure

Names and placement are part of "done," not cosmetic. Name every file/artifact by **what it contains or does**,
never by the batch that created it — no `b##-*` / batch-named catch-alls (meaningless to a future reader, and they
collect unrelated things into a grab-bag). Follow the **existing convention of the directory** you're adding to
(e.g. `k8s/argocd/applications/` is category-named — helm-apps / subdir-apps / loose-apps / raw-extras); put each
thing in the file its type belongs to instead of inventing a new bucket. A batch-named or miscategorized file is
drift, and gets cleaned up like any other drift.

## Cross-cutting: one source of truth for a cross-surface taxonomy (possible process)

Some bodies of work introduce a **classification that must hold identically across more than one surface** — e.g.
the B82 application taxonomy (which apps are data-owning **Applications**) spans **DataHub** (Application entities),
**Port** (the `component` / `k8s_workload` catalog), the **docs** (arch + a concept page), and the **diagrams**
(LikeC4 + platform-map). When that happens, do **not** re-encode the classification per surface — that is exactly how
drift starts. Define it **once** as a canonical, machine-readable **registry** (a single YAML/JSON/table that IS the
source of truth), and make every surface **consume or DoD-check against that one registry**. If a thing isn't in the
registry, it isn't in any surface — drift becomes impossible **by construction**, not by discipline.

**Onboarding a new app (standing close-out rule).** The moment a body of work stands up a **new deployed service**
— a pod, a UI, a runner, an nginx — it is **not done until it is registered in `applications.yaml`** (the live B82
registry): add a `port_component` entry (pure-compute → `datahub_application: false`; owns cataloged data → `true`
with `owns` URN patterns), then `tofu apply` the Port catalog (+ `emit_applications` for DataHub if it's data-owning)
and confirm `scripts/check-app-registry.sh` is green. A new service that ships without a registry entry is drift by
definition — Port and DataHub silently fall out of sync with what's actually running. The same onboarding also covers the **operational surfaces** (§6 operational
completeness): an **Uptime Kuma monitor** (LAN health → the `uptime_monitor` Port blueprint) **and** a **Prometheus
`*Down` alert** (a `PrometheusRule`, like every other service carries) — a service the catalog knows about but nothing
watches is only half-onboarded. Applies to every change that deploys a new app; the registry entry, the drift-guard
pass, the **Kuma monitor**, and the **Down alert** are all part of that change's close-out. (Example: `ge-docs`, the GE
Data Docs server — registered here as a pure-compute `ui` component, with a Kuma monitor + `GeDocsDown` rule, when its
build lands.)

This is a **possible process**: reach for it whenever the same set of things must be classified identically in **≥2
surfaces** (Port ↔ DataHub ↔ docs ↔ diagrams). Skip it for single-surface work. When it applies, the registry is the
deliverable the other surfaces are graded against in the drift sweep above.

## Why

Every capability must be **placed** (arch/diagrams), **operable** (runbook/api/hosts), **demonstrable** (UI+CLI
demo, executed), **investigable** (sequence diagram + history), **reversible** (cleanup), **closed out** (Linear +
backlog), **operationally durable** (reproducible / secret-restorable / monitored / backed-up / triggered), and
**scanned** (the security / code-quality gate, findings triaged not ignored).
Add all eight pillars as explicit acceptance criteria in every design/plan doc.

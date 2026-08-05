# Definition of Done

The weyland Definition of Done — the hard gate every body of work passes before it's "done." This page is the
**canonical, published** version (the RAG corpus + the shared reference); it supersedes any private note. A
capability is **NOT done** until ALL six pillars hold. "Ran once" ≠ done.

> Added 2026-07-14; grown through B64 (render-verify), B69 (operational completeness), B111 (metrics-scrape
> ServiceMonitor + Grafana dashboard made explicit monitoring criteria), 2026-08-05 (tier rebalance at close-out —
> keep High/Medium/Low roughly equal), and 2026-08-05 (B82 — one source of truth for a cross-surface taxonomy).
> Applies retroactively and going forward.

## 1. Documentation sweep (every batch)

- **arch.md** — a **substantial** entry: comparative placement (why this vs the alternatives), a decision
  matrix/tradeoffs, and diagrams. Not a one-line entry — `arch.md` is a deliverable.
- **api.md + hosts.md** — updated for EVERY endpoint / host / IP / DNS / subdomain change.
- **schedules.md** — updated for any new timer.
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
  is **not done** (🟡, not ✅). This is the anti-fabrication guarantee.
- **Enforcement (per batch, at close-out):** audit every completed item against the `docs/demos/README.md` ledger
  **as part of the close-out** (same step as the Linear sync) — a new/changed capability with no ledger row, or a
  stale one, is **not done**. (This check is what surfaced the B70/B94 demo gaps on 2026-07-23.)

## 4. Cleanup / teardown

- Any demo that CREATES data ships a teardown that removes it. Read-only demos say so.

## 5. Close-out / tracking (the unit isn't done until the tracker says so)

- **Linear** — flip the tracked issue (`EMA-*`) to Done with a completion comment (what shipped, gotchas, links).
- **backlog.md** — flip the item to ✅ DONE with a substantial summary (backlog = ordered source; Linear = status).
- **Memory** — capture any durable, non-obvious lesson.
- **Tier rebalance — keep High / Medium / Low roughly equal.** Completing work drains the **High** lane, so at
  close-out re-tier to refill it: promote the strongest **Medium → High**, then backfill **Low → Medium** (and, as
  the tail grows, close or promote stale **Low** items — a Low that never rises is a drop candidate). It's a pull
  system: High pulls from Medium, Medium pulls from Low. Apply the move in **both** `backlog.md` (the 🔴/🟡/⚪ tag) and
  **Linear** (priority field + the `High`/`Medium`/`Low` label), in the **same** close-out step as the status flip —
  the two must never diverge. This keeps the roadmap from silently emptying High while Low accumulates. Judgment, not
  arithmetic: "roughly equal," re-derived from the current open set, not forced to exact counts.

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

This is a **possible process**: reach for it whenever the same set of things must be classified identically in **≥2
surfaces** (Port ↔ DataHub ↔ docs ↔ diagrams). Skip it for single-surface work. When it applies, the registry is the
deliverable the other surfaces are graded against in the drift sweep above.

## Why

Every capability must be **placed** (arch/diagrams), **operable** (runbook/api/hosts), **demonstrable** (UI+CLI
demo, executed), **investigable** (sequence diagram + history), **reversible** (cleanup), **closed out** (Linear +
backlog), and **operationally durable** (reproducible / secret-restorable / monitored / backed-up / triggered).
Add all six pillars as explicit acceptance criteria in every design/plan doc.

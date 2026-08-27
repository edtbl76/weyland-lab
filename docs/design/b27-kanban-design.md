# B27 — Hermes Kanban: self-management + roadmap co-pilot — design

**Status:** DESIGN — finalized 2026-06-17 (live verification complete). **Depends on:** B2 (Hermes),
B26 (LiteLLM gateway = the planning brain), the weyland system-view MCP.
**Goal:** turn Hermes from one-shot reason→act turns into an agent that **decomposes, plans, and tracks
multi-step work on a board** — for (a) its own tasks and (b) the weyland roadmap.

## Scope (both, one body of work)
- **(a) Self-management** — Hermes plans/tracks its own multi-step tasks. Foundation.
- **(b) Roadmap co-pilot** — a board mirrored from *this backlog*: agent-assisted execution tracking.

## Decisions (finalized after live verification, 2026-06-17)
- **Board: Hermes's native durable SQLite Kanban** — **built in, no new container, lives in CT 104.**
  *Supersedes the earlier "Postgres board" idea:* the native board is far richer than anything we'd build
  (boards-per-project, task dependencies, atomic claims, named-profile **workers in isolated workspaces**, a
  gateway **dispatcher**, **`swarm`** = parallel workers→verifier→synthesizer, **`decompose`/`specify`** =
  auto fan-out). Rebuilding that in Postgres would be worse and lose all of it. SQLite `kanban.db` is durable
  + queryable. **→ No Postgres `kanban` schema, no custom MCP board, no new infra.**
- **Planning brain: Gemini free via the gateway** — alias **`gemini-flash`** (`gemini-2.5-flash`: $0,
  generous free quota, fast, reasons); `gemini-pro` as the stronger fallback. **$0 — no paid models.** Pinned
  to the **two planning aux lanes only**; default brain + workers stay local `qwen3-coder`.
- **`backlog.md` → `docs/backlog.md`** (build step 1) — git-tracked + RAG-ingested, and the source the
  roadmap-sync script reads.
- **Plan-only → autonomous** progression.

## Verification results (CT 104 + gateway, 2026-06-17)
1. **Native Kanban = durable SQLite** (`kanban.db` via `hermes kanban init`); dispatcher runs in the existing
   `hermes-gateway` systemd service. **No Postgres, no container.** Rich subcommands: `boards`, `create`,
   `link` (deps), `claim`, `decompose`, `specify`, `swarm`, `dispatch`, `watch`, `stats`, `notify-*`, …
2. **Planning turns are pinnable:** `decompose` → `auxiliary.kanban_decomposer`, `specify` →
   `auxiliary.triage_specifier`. Point both at the gateway Gemini provider; everything else stays local
   (the lanes we already pinned). No `/model` juggling.
3. **Model:** `gemini-flash`/`gemini-pro` exposed by the gateway (Gemini source has 37 models in
   `model_catalog`). $0 free tier.

## Architecture

### Board — native Hermes Kanban (CT 104, SQLite)
`hermes kanban init` creates `kanban.db`. One board per workstream (`hermes kanban boards`). Tasks carry
dependencies, comments, events; the gateway dispatcher promotes ready tasks and spawns **profile workers in
isolated workspaces**. Triage-column tasks get fleshed out by `specify` or fanned out by `decompose`.

### (a) Self-management flow
DM a multi-step task → it lands in triage → **`specify`/`decompose` run on Gemini (gateway)** → ready tasks →
**workers execute on local `qwen3-coder`** in isolated workspaces → `complete`. *Planning = Gemini (cloud,
free); execution = local.* Clean split: the expensive reasoning is the cheap-to-offload part.

### (b) Roadmap co-pilot — a `weyland-roadmap` board synced one-way from `docs/backlog.md`
- **Sync script on CT 104** (cron/manual): fetch raw `docs/backlog.md` from the **public GitHub repo** (a
  `curl` of the raw file — no full clone needed) → parse `### B27 —`/`### U13 —` headings + DONE/status
  markers → **upsert tasks** via the `hermes kanban` CLI (`create`/`edit`/`complete`/`block`). Idempotent.
- **Ownership:** the human owns `backlog.md` (source of truth); the sync drives the backlog-derived fields;
  the agent's **own** comments / board-status moves are its tracking layer. **The agent never edits
  `backlog.md`.** One-way only.

### Brain wiring (CT 104)
Add a `custom` provider via `hermes model` → gateway (`http://192.168.1.243:30400/v1`, api_key =
`LITELLM_MASTER_KEY`, model `gemini-flash`, api_mode `chat_completions`). Then set
`auxiliary.kanban_decomposer.provider` + `auxiliary.triage_specifier.provider` to that provider in
`~/.hermes/config.yaml`. Leave `model.default` = `qwen3-coder:30b` and the local-pinned lanes untouched.

## Governance / risk
- Kanban actions **and worker execution are Hermes-internal** (CT 104 sandbox) — **not** wrapped by the
  tool-server `/mcp-act` guardrails. The real act surface is **workers running shell in CT 104's isolated
  workspaces.** Acceptable for a single-user LAN lab; **if a worker ever reaches the cluster** (kubectl,
  tool-server act-tools), that's where B14/B17 act-governance must re-enter. Keep workers' reach scoped to
  CT 104 for v1.
- One-way sync = human stays roadmap source of truth.
- $0: planning is low-volume (a few `decompose`/`specify` calls a day), so Gemini's free quota is ample;
  `gemini-pro` fallback if `flash`'s plans are weak; OpenRouter `gpt-oss-120b:free` as a third option.

## Phasing
1. **`backlog.md` → `docs/`** + repoint the "canonical source" refs (`aidlc-state.md`, running list); note the
   now-dangling links to gitignored `aidlc-docs/construction/*`.
2. **(a) self-management** — wire the gateway provider, pin the two planning aux lanes to Gemini,
   `hermes kanban init`. Validate: a multi-step DM triages → decomposes (Gemini) → a worker executes locally.
3. **(b) roadmap co-pilot** — create the `weyland-roadmap` board + the CT-104 sync script (one-way from
   `docs/backlog.md`). Validate: Hermes answers "state of B35?" from the board; tracks exec status.
4. **Optional later** — surface the board to Telegram (`/kanban` adapter, `notify-subscribe`) for push updates.

## Open questions
- Worker execution brain: local `qwen3-coder` (default) — fine; revisit if execution quality lags.
- Sync cadence: start manual or a simple CT-104 cron; real-time isn't needed (the backlog changes slowly).
- Whether roadmap-board completions should notify you (`hermes kanban notify-subscribe`) vs stay silent.

## As-built (2026-06-17) — DONE
Shipped both (a) + (b). Deltas from the design above, learned during bring-up:
- **`hermes model` wizard clobbers the default** — it set `gemini-flash` as the *default brain* (would route
  every turn off-LAN). Reverted `model.default`/`base_url`/`api_key` to local `qwen3-coder`; the gateway
  provider (`weyland-model-gateway`) stays *available* for the pinned planning lanes only.
- **`--initial-status blocked` doesn't stick** — Hermes auto-unblocks a card with no real blocker → it drifts
  to `ready`. **Safety actually rests on roadmap cards being `unassigned`:** the dispatcher only runs
  *assigned* tasks, so unassigned cards are a passive mirror (verified: `running 0` while the `default` worker
  was busy on assigned tasks). The sync sets no `--assignee` by design.
- **`decompose` autonomously executes** — confirmed: a wiring-test task fanned into children assigned to
  `default` and workers *started running shell* in CT 104 to build it. Powerful for (a); the reason (b) had to
  be execution-proof. Reinforces the governance note: keep workers' reach inside CT 104.
- **First sync:** 38 cards (13 done / 23 active-ready / 2 dropped skipped). Status resolved doc-wide
  (top "## DONE" bullets + priority markers), not just the detail body — `roadmap-sync.py` `build_status_map`.
- Sync = `nodes/weyland/hermes/roadmap-sync.py` on CT 104 (`/root/`), cron `17 */6 * * *`.
- Runbook: [../runbooks/agent-hermes.md](../runbooks/agent-hermes.md) §Kanban.

**Open/optional (not blocking DONE):** Telegram `/kanban` push (`notify-subscribe`); a real-time sync trigger
(B30-style) instead of 6h cron; per-card title refresh on re-sync (idempotency-key dedups create but keeps the
original title).

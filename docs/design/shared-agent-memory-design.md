# Shared Agent Memory — Design (B182)

**Status: DECIDED + BUILT (2026-10-03)** — Basic Memory on rogueone, serving the existing notes in place; see
"Decisions". Runbook: [../runbooks/shared-agent-memory.md](../runbooks/shared-agent-memory.md).
Tracking: backlog **B182**, Linear **EMA-240**. Concept: [../concepts/multi-harness.md](../concepts/multi-harness.md).

## Goal

The lab is multi-harness (Claude Code, Codex, OpenCode, Cline, Pi, Open WebUI, weyland-operator). Give all of them
**one** memory store they read and write, so a decision, lesson or correction learned through one harness is
available in every other — with **no second copy that can drift**.

## Current state (2026-09-25)

| Layer | Where it lives | Which harnesses see it |
|---|---|---|
| **Rules / conventions** | `AGENTS.md`, `CLAUDE.md`, `docs/`, AIDLC `aidlc/spaces/default/memory/*.md` | every harness that reads the repo (Codex/OpenCode/Pi read `AGENTS.md`; Claude Code reads `CLAUDE.md`) |
| **Working memory** (lessons, decisions, corrections, references) | Claude Code auto-memory: `~/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/memory/` — ~190 Markdown notes + a `MEMORY.md` index, frontmatter (`name`/`description`/`type`) + `[[wikilinks]]` | **written by Claude Code only**; since 2026-09-25 `AGENTS.md` points other rogueone harnesses at the index read-only (a stopgap); local to rogueone, not in git, backed up only by restic |
| **Operator session memory** | Postgres (`weyland-operator`, per Telegram session) | the operator only; conversational state, not lessons |
| **Retrieval corpus** | `context_ask` / `context_search` (the lab RAG over docs + knowledge repos) | any MCP client of the tool-server / Bifrost — read-only, rebuilt from sources |

Failure mode this fixes: a lesson recorded in Claude's memory is invisible to Codex (connected to Linear 2026-09-25),
so Codex can re-propose what was already rejected — the same drift class as the KEDA and Cyrus re-proposals, but
across harnesses instead of across sessions.

## Components (all decided 2026-10-03 — see Decisions)

| Component | Options on the table | Status |
|---|---|---|
| **Store** | **Basic Memory** (AGPL-3.0; Markdown files + SQLite index, Postgres optional; `[[wikilinks]]`) · MCP reference `memory` server (MIT; JSONL knowledge graph) · mem0 **OpenMemory** (self-hosted, local-first; also a hosted variant) · Graphiti (temporal knowledge graph) · ~~ContextStream~~ (rejected) | **Decided: Basic Memory** |
| **Transport** | streamable HTTP (reachable by a gateway and by harnesses on other hosts) · stdio (local-only; one process per harness — concurrency risk) | **Decided: streamable HTTP** |
| **Gateway** | **Bifrost MCP gateway** (Claude Code, Codex and OpenCode already connect to it) · the governed MCP gateway (operator's path, Keycloak `client_credentials`) · direct per-harness MCP config | **Decided: Bifrost** |
| **Host** | mother (k8s, always-on, backed up) · rogueone (where the agents run; **always on** — the operator's interface, owner 2026-10-03) | **Decided: rogueone** |
| **Source of truth for the notes** | git-tracked Markdown in this repo · a separate private repo · the store's own DB | **Decided: the files, in place** |
| **Migration of Claude's memory** | point the store at the existing directory · move the directory into the store and have Claude Code use the store's tools · keep Claude's native memory as a cache of the shared store | **Decided: in place (symlink)** — ONE store |
| **Write policy** | any harness writes · writes gated/reviewed · per-harness namespaces + one shared namespace | **Decided: coding agents write, operator reads** |

## Constraints (fixed — these are not TBD)

- **$0.** Free forever, not a trial. Cloud is acceptable **if free** (decided 2026-09-25); self-hosted is not a
  requirement on its own.
- **One store, not two.** Any option that leaves Claude's memory and the shared store as parallel copies fails.
- **Harness-neutral.** Reachable over MCP (every harness except Pi speaks MCP today; Pi uses the files directly).
- **Readable without the tool.** The notes stay human-readable text (Markdown/JSONL), so losing the server never
  loses the memory.
- **Fail closed.** A harness that cannot reach the store must say so, never proceed as if memory were empty.
- **Secrets never enter memory.** Same rule as the rest of the lab: no tokens, keys or passwords in notes.

## Evaluation criteria (for the decision)

1. Concurrent writes from two harnesses at once (Claude Code + Codex) — no lost or corrupted note.
2. Retrieval quality: finds the relevant note from a natural question (the `MEMORY.md` index + wikilinks today).
3. Transport reachable from a gateway (HTTP) or not.
4. License fit (AGPL is acceptable for internal, unmodified use; note it if the lab ever modifies and serves it).
5. Operational cost on mother (memory/CPU — mother is at its RAM ceiling, see B134).
6. Backup/restore story (git, or the lab's MinIO backup lane).

## Rejected

| Option | Why |
|---|---|
| **ContextStream** (2026-09-25) | Free tier is real (10k credits/mo, 15 projects) and cloud is fine when free, but per-operation credit cost is unpublished and it is a second, proprietary store — duplication, not the fix. Its code-intelligence half duplicates Sourcebot/Zoekt, graphify and Serena. |

## Verification evidence — Basic Memory 0.23.2 (2026-10-03)

Run in a throwaway `python:3.12-slim` container on rogueone, as the invoking user, against a **copy** of the real
memory directory (213 notes). Probe: an MCP client over streamable HTTP (`basic-memory mcp --transport
streamable-http`). Nothing touched the live directory or the cluster.

| Check | Result |
|---|---|
| Streamable HTTP (Bifrost-reachable transport) | **Pass** — 21 MCP tools (`search_notes`, `read_note`, `write_note`, `edit_note`, `build_context`, `recent_activity`, …) |
| Indexes the existing notes in place | **Pass** — all 213 indexed in ~20 s; frontmatter + `[[wikilinks]]` read as-is |
| **Leaves the files alone** | **Fail by default, pass when configured** — the defaults REWROTE 207 of 213 notes on first index (added `permalink:`, re-wrapped long `description:` lines, changed timestamps `2026-08-24T15:01:54.273Z` → `2026-08-24 15:01:54.273000+00:00`, prepended a frontmatter block to `MEMORY.md`). With `disable_permalinks=true` + `ensure_frontmatter_on_sync=false`: **0 of 213 rewritten** |
| A plain-file edit (how Claude Code writes memory) is picked up | **Pass** — a note written straight to disk was searchable within seconds |
| Two clients writing at the same moment | **Pass** — both notes written, both intact |
| Search finds the right note (5 questions with a known answer, top 5) | **3/5 with semantic search, 2/5 keyword-only.** Missed: KEDA → `store-scaler-easy-button`, "trigger CI without cron" → the canonical-op-command note |
| Rejects a token-shaped write | **Fail** — accepted a `ghp_…` string. A guard is needed outside the store (hook or scan) |
| Server memory | **1.4 GB** with semantic search (local `bge-small-en-v1.5` via fastembed); **268 MB** keyword-only. Semantic can instead call an OpenAI-compatible embedding endpoint (`semantic_embedding_api_base`) |
| License | AGPL-3.0 — fine for internal, unmodified use |

Not yet tested: the other store candidates. The reference `memory` server (JSONL graph), OpenMemory and Graphiti
all keep their own store format, so each would be a **second copy** of the Markdown notes — the shape the "one
store" constraint rules out. That is from their documented architecture, not a run.

## Decisions

| Date | Component | Decision | Alternatives rejected | Evidence |
|---|---|---|---|---|
| 2026-10-03 | **Store** | **Basic Memory 0.23.2** (AGPL-3.0), frozen in `nodes/rogueone/basic-memory/requirements.txt` | reference `memory` server, OpenMemory, Graphiti — each keeps its own store format, i.e. a second copy of the notes | the verification table above |
| 2026-10-03 | **Source of truth for the notes** | **The Markdown files themselves**, moved to `~/agent-memory/weyland/` (harness-neutral); Claude Code's memory path is a **symlink** to it. One copy, no sync | git-tracked notes synced to replicas (owner: git is slow with extra hops, and memory must not leave the LAN); a mother-side replica (pointless once rogueone is always on) | 214 files moved, checksums identical before/after; the service changes 0 of them |
| 2026-10-03 | **Migration of Claude's memory** | Point the store at the existing notes **in place** — Claude Code keeps native memory (always-loaded `MEMORY.md`, plain-file writes) | retire native memory and write only via MCP (loses the always-in-context index) | `check-shared-memory.py` step 4: a plain-file note is searchable in < 1 s |
| 2026-10-03 | **Host** | **rogueone** (user unit `basic-memory.service`) | mother — would force native memory to retire or a synced second copy; also mother's RAM ceiling (B134) | rogueone always on (owner); 1.5 GB RSS vs ~101 GB free |
| 2026-10-03 | **Transport + gateway** | **Streamable HTTP on :8765**, registered in **Bifrost** as `Agent_Memory`; coding-agents key = all 21 tools, operator key = read-only | stdio per harness (one process each, no shared server) | Bifrost logs `Connected to MCP server 'Agent_Memory'`; Codex's exact route + key found a Claude-written note and wrote one that landed in Claude's dir, both < 1 s |
| 2026-10-03 | **Access control** | Basic Memory has no auth → **ufw on rogueone admits only mother (192.168.1.243) to :8765**; everything else on rogueone unchanged (default allow, forwarding ACCEPT) | an authenticating proxy in front (more moving parts for one LAN client) | from a mother pod: reached; from a non-mother source (a Docker container on rogueone): blocked |
| 2026-10-03 | **Write policy** | Any coding agent writes; the operator recalls only. Secrets are FLAGGED, not rejected: `agent-memory-watch` (gitleaks every 15 min → Kuma) | rejecting at write time (Basic Memory has no hook for it) | the store accepted a `ghp_…` note; gitleaks 8.21.2 flags one, passes a clean note |
| 2026-10-03 | **Pi** | Out of scope for MCP; it can read/write the files directly (same host) per `AGENTS.md` | a wrapper | — |

## Open questions

- **Answered 2026-10-03:** Bifrost registers it (streamable HTTP, verified live). Claude Code keeps native memory —
  its path is a symlink to the store. Pi: direct file access, no MCP.
- **Operator — decided + built 2026-10-03 (option A):** memory joins the compositor fleet as a READ-ONLY upstream, so
  the operator recalls through the same governed gateway (`/mcp-fleet`, Keycloak actor) as every other read tool. The
  alternative — the operator calling Bifrost with the read-only operator key — was rejected: a new sealed secret, a
  second tool source in the operator, and the key also carries Excalidraw/Malwarebytes. The allowlist is enforced by
  compositor middleware (hide + refuse; 7 read tools) because FastMCP 3.4.5's `include_tags` config filtered out
  everything. The operator's local brain gets `memory_search_notes` + `memory_read_note` in `LOCAL_FLEET_ALLOW`.
- **Open WebUI — decided + built 2026-10-04 (owner):** it recalls through the governed MCP gateway as EACH PERSON.
  Open WebUI (0.10.2, native MCP tool servers) connects to `/mcp-memory` with `system_oauth`, which forwards the
  signed-in user's own Keycloak token; the gateway validates it and sets `X-Forwarded-User` (the person) beside
  `X-Forwarded-Consumer` (the client). `/mcp-memory` routes to a memory-ONLY compositor (same image, every other
  upstream off), so chat users get the 7 read tools with the operator's guarantees (writes hidden + refused, semantic
  search, invented filters dropped) — not the 102-tool fleet, which Open WebUI cannot filter per connection.
  **Rejected:** a Bifrost virtual key — one shared identity for every person ("bad juju for security", owner) and a
  stored secret, and it bypasses the compositor fixes the operator needed to answer correctly. This mirrors a real
  architecture: user identity propagated from the IdP through the gateway to the backend.

## Architecture placement

`sharedMemory` sits under **rogueone** in the LikeC4 model (moved 2026-10-03): Claude Code reads/writes its files
directly; Codex and the other coding agents reach it through Bifrost; the operator recalls via `/mcp-fleet` and
Open WebUI via `/mcp-memory` (both through the governed MCP gateway). Flow: [../diagrams/flow-shared-memory.md](../diagrams/flow-shared-memory.md).

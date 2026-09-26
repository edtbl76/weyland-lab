# Shared Agent Memory — Design (B182)

**Status: PROPOSED — every component is TBD.** This record exists so the architecture shows the component and its
open decisions *before* anything is built. Nothing here is decided until the "Decisions" table says so.
Tracking: backlog **B182**, Linear **EMA-240**. Concept: [../concepts/multi-harness.md](../concepts/multi-harness.md).

## Goal

The lab is multi-harness (Claude Code, Codex, OpenCode, Cline, Pi, Open WebUI, weyland-operator). Give all of them
**one** memory store they read and write, so a decision, lesson or correction learned through one harness is
available in every other — with **no second copy that can drift**.

## Current state (2026-09-25)

| Layer | Where it lives | Which harnesses see it |
|---|---|---|
| **Rules / conventions** | `AGENTS.md`, `CLAUDE.md`, `docs/`, AIDLC `aidlc/spaces/default/memory/*.md` | every harness that reads the repo (Codex/OpenCode/Pi read `AGENTS.md`; Claude Code reads `CLAUDE.md`) |
| **Working memory** (lessons, decisions, corrections, references) | Claude Code auto-memory: `~/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/memory/` — ~190 Markdown notes + a `MEMORY.md` index, frontmatter (`name`/`description`/`type`) + `[[wikilinks]]` | **Claude Code only**; local to rogueone, not in git, not backed up by anything but restic |
| **Operator session memory** | Postgres (`weyland-operator`, per Telegram session) | the operator only; conversational state, not lessons |
| **Retrieval corpus** | `context_ask` / `context_search` (the lab RAG over docs + knowledge repos) | any MCP client of the tool-server / Bifrost — read-only, rebuilt from sources |

Failure mode this fixes: a lesson recorded in Claude's memory is invisible to Codex (connected to Linear 2026-09-25),
so Codex can re-propose what was already rejected — the same drift class as the KEDA and Cyrus re-proposals, but
across harnesses instead of across sessions.

## Components — all TBD

| Component | Options on the table | Status |
|---|---|---|
| **Store** | **Basic Memory** (AGPL-3.0; Markdown files + SQLite index, Postgres optional; `[[wikilinks]]`) · MCP reference `memory` server (MIT; JSONL knowledge graph) · mem0 **OpenMemory** (self-hosted, local-first; also a hosted variant) · Graphiti (temporal knowledge graph) · ~~ContextStream~~ (rejected) | **TBD** |
| **Transport** | streamable HTTP (reachable by a gateway and by harnesses on other hosts) · stdio (local-only; one process per harness — concurrency risk) | **TBD** — depends on the store |
| **Gateway** | **Bifrost MCP gateway** (Claude Code, Codex and OpenCode already connect to it) · the governed MCP gateway (operator's path, Keycloak `client_credentials`) · direct per-harness MCP config | **TBD** — Bifrost is the leading candidate, not a decision |
| **Host** | mother (k8s, always-on, backed up) · rogueone (where the agents run; not always-on) | **TBD** |
| **Source of truth for the notes** | git-tracked Markdown in this repo · a separate private repo · the store's own DB | **TBD** |
| **Migration of Claude's memory** | point the store at the existing directory · move the directory into the store and have Claude Code use the store's tools · keep Claude's native memory as a cache of the shared store | **TBD** — must end with ONE store |
| **Write policy** | any harness writes · writes gated/reviewed · per-harness namespaces + one shared namespace | **TBD** |

## Constraints (fixed — these are not TBD)

- **$0.** Free forever, not a trial. Cloud is acceptable **if free** (decided 2026-09-25); self-hosted is not a
  requirement on its own.
- **One store, not two.** Any option that leaves Claude's memory and the shared store as parallel copies fails.
- **Harness-neutral.** Reachable over MCP (every harness except Pi speaks MCP today; Pi needs a path or is out of
  scope — TBD).
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

## Decisions

None yet. Record each decision here with date, the option chosen, the alternatives rejected, and the evidence
(a test against the real tool, not its README).

## Open questions

- Does Basic Memory serve streamable HTTP in a form Bifrost can register as an MCP client? (HTTPS client config is
  documented; verify against a running server.)
- Can Claude Code's auto-memory be pointed at an external store, or does "one store" mean Claude Code uses the
  store's MCP tools and its native memory is retired?
- Does Open WebUI need write access, or read-only recall?
- Pi has no MCP support configured — include via a wrapper, or out of scope?

## Architecture placement

The LikeC4 model places `sharedMemory` at the **model root** (host TBD) with **planned** edges from Claude Code,
Codex, the coding agents, the operator and Open WebUI; view `harnesses`. Once the host and gateway are decided, move
the element under its host and replace the planned edges with the real path.

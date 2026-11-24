# Shared context for many humans and agents — Design (B256)

**Status: design approved, skeleton built (2026-11-23), Linear EMA-357.** The owner approved the design and the
skeleton ("yes"); the ADR follows the live end-to-end proof. Builds on B182
([shared-agent-memory-design.md](shared-agent-memory-design.md)); does not replace Basic Memory, Linear or git.

## Why

The lab's shared context is built for one human and their agents. B182's memory works because one person writes it
and every agent follows `AGENTS.md`. Owner, 2026-11-20: "I'd also like to potentially create shared-context structure
for multi-player environments where multiple humans and agents can collaborate." B257 (Herdr, adopted 2026-11-23)
makes several agents side by side a practical setup now, and B255 measured what stale and oversized context costs.

## Scenarios

Each names who reads, who writes, and what must never leak. "Owner" is Edward; "a second human" is a hypothetical
collaborator with their own Keycloak account (onboarding real users is out of scope).

### S1. Two coding agents on one backlog item

Claude Code and Codex in side-by-side Herdr panes on one B-item: one builds, the other reviews or tests.

| | |
|---|---|
| Read | both: global rules (`AGENTS.md`), project memory (the notes), the item (Linear, backlog), each other's task notes |
| Write | both: task notes for the item (what was tried, decided, left open); a durable lesson into project memory |
| Must not | silently overwrite each other's note (both edit "B256 progress" at once); lose which agent wrote which finding |
| Breaks today | both write through the same Bifrost `coding-agents` key, or as files (Claude Code), so a note has no author; concurrent edits are last-writer-wins |

### S2. The owner and a second human review an agent's work

An agent finished an item; the owner and a second human read its hand-off, comment, and decide.

| | |
|---|---|
| Read | both humans: the hand-off record, project memory, Linear. The second human's agents: the same shared layers |
| Write | each human: review notes and decisions; their own personal notes. The agent: its hand-off record |
| Must not | the second human's personal notes reach the owner's agents (or the reverse); either human's agents rewrite global rules (`AGENTS.md`) or the other's decisions; an agent's claim be mistaken for a human decision |
| Breaks today | there is one person's store; no personal layer; any coding-agent key can write every note; no field says whether a fact came from a human or an agent |

### S3. The operator, the Realm and a coding agent share an incident

An alert fires; the operator (Telegram) triages, the Realm investigates, a coding agent fixes.

| | |
|---|---|
| Read | all three: project memory (runbook lessons); the incident's notes. The owner: everything |
| Write | the coding agent: findings and the fix as incident notes, then a durable lesson. The operator and the Realm: findings into the incident record (today they are read-only) |
| Must not | Telegram conversation text (operator session memory, Postgres) or any secret printed in a log enter shared memory; the incident's working notes outlive the incident as if they were durable facts |
| Breaks today | the operator and the Realm cannot write at all (read-only by design); no incident or task scope, so working notes and durable lessons mix in one flat directory; gitleaks flags secrets only after they land (every 15 minutes) |

## Inventory (what exists, 2026-11-23)

| Piece | What it gives several people and agents | Where it breaks |
|---|---|---|
| **The notes** (`~/agent-memory/weyland/`, 290 Markdown files, one fact each; `MEMORY.md` core + `MEMORY-catalog.md`, B182/B255) | one store every harness reads; human-readable; links between facts | flat: no task, incident or personal scope; no author field (249 notes carry Claude Code's `originSessionId`, a session id, not an identity); not in git, so the only history is the nightly restic backup |
| **Basic Memory 0.23.2** (`basic-memory.service`, `:8765`, B182) | MCP read and write tools over the notes; concurrent writes of *different* notes are safe (tested 2026-10-03) | no authentication (ufw admits only mother); no permissions; an edit of the same note is last-writer-wins; accepts a token-shaped string |
| **Bifrost `Agent_Memory`** (MCP client; per-key tool allowlists, B182/B203) | a per-key split: `coding-agents` = all 21 tools, operator key = read-only | the key is shared: Codex and the other agents on it are one identity; no per-agent or per-person rights; no record of which tool call wrote what |
| **Claude Code native memory** (its memory path is a symlink to the notes) | always-loaded index; plain-file writes | writes bypass every gateway: no identity, no audit |
| **Governed MCP gateway** `/mcp-memory`, `/mcp-fleet` (Keycloak JWT; `X-Forwarded-User` = person, `X-Forwarded-Consumer` = client; anti-spoof) | real per-person identity for Open WebUI users and the operator; one audit line per request (`mcp-gateway-audit … actor= user= status=`) | read-only behind it (the compositor hides and refuses write tools); the audit line names the path, not the tool or what changed |
| **Linear** (team EMA) + `docs/backlog.md` | shared status, acceptance criteria, comments with an author | not a memory: an agent picking up work reads prose comments; no structured "tried / decided / open" record |
| **git + ADRs** (`docs/adr/`) | durable decisions with author, history, review | the owner does all git; agents cannot record a decision there themselves |
| **Langfuse sessions** (B249 session id per dispatch) | who called which model in one conversation | traces, not shared facts; content-heavy, may hold user text |
| **Bifrost Agent Logs** (`x-bf-session-id`, `contextId`, B249) | joins a conversation's tool calls | per-request logs, not a store |
| **Harness session context** (Claude Code transcripts and compaction summaries, Codex sessions) | each harness's own memory of the current work | private to one harness and session; a summary is the only hand-off (B255) |
| **Herdr socket** (B257) | one agent can prompt another and wait for it | carries prompts, not a record; nothing persists what was handed over |
| **`agent-memory-watch`** (gitleaks every 15 minutes) + `check-shared-memory.py` (index budget, links) | catches a secret or a broken index after it lands | after the fact; any new layer must be inside its scan |

**The gap in one line:** reads already have identity (the governed gateway), writes do not; and the store has one flat
scope, no author on a fact, and last-writer-wins on the same note.

## Field survey (2026-11-23)

Primary sources only (23 read; list below). **Finding:** no product ships provenance, scoped write rights, conflict
handling and expiry together on plain Markdown. Every product that has them is paid cloud (Basic Memory Teams, Letta
shared repositories) or a new store (Graphiti, Mem0). The ideas layer onto Basic Memory behind the governed gateway.

| Approach | Source (date) | What it offers | Verdict | Reason |
|---|---|---|---|---|
| Basic Memory, local | github.com/basicmachines-co/basic-memory (undated) | Markdown + frontmatter; schema notes (`type: schema`) that warn, or error in strict mode; no auth, permissions or author; history "roll your own" | **ADOPT** (keep) | the base; its schema tools can require provenance fields |
| Basic Memory Teams / Cloud | docs.basicmemory.com teams, file-history, review-runs (undated) | per-project roles (Viewer, Editor, Admin); `updated_by` in frontmatter; file history; an old version can't be applied if the note changed since; a review queue for agent runs with undo | **ADAPT** ideas, reject product | paid cloud; copy `updated_by`, the version check, the review idea |
| Graphiti / Zep | arxiv.org/abs/2501.13956 (2025-01-20); github.com/getzep/graphiti | bi-temporal facts (`t_valid`/`t_invalid`, created/expired); contradictions invalidate, never delete; each fact traces to its source episode; `group_id` scopes with no access control | **ADAPT** | take supersede-not-delete and validity dates as frontmatter; the product is a new store plus LLM extraction |
| Mem0 scopes | docs.mem0.ai/core-concepts/memory-types (undated) | memories scoped by `user_id`, `agent_id`, `run_id`; changed facts stored beside old ones | **ADAPT** ideas | another store; the three scope axes map onto directories |
| Letta shared memory blocks | docs.letta.com/guides/agents/multi-agent-shared-memory (undated, legacy) | one block for many agents; `insert` (append) is concurrency-safe, `replace` fails if the text changed, `rethink` is last-writer-wins; advice: one owner per heavily edited block | **ADAPT** | write classes by concurrency risk |
| Letta shared repositories (git) | docs.letta.com/concepts/shared-memory (undated) | shared memory is a git repo; agents commit and push | **ADAPT** idea | git gives author and history per write; the product is cloud-only |
| Claude Code memory hierarchy | code.claude.com/docs/en/memory (undated) | managed, project, user and local tiers, concatenated; path-scoped rules; enforcement belongs in settings, not prose | **ADOPT** the model | the same tiers for memory scopes, enforced at the gateway |
| Anthropic memory tool | platform.claude.com/…/memory-tool (undated) | client-side storage mapped per user; `create` fails if the file exists; delete files not accessed in a long time; block path traversal | **ADAPT** | per-identity paths, create-fails-if-exists, an expiry sweep |
| Progress-file hand-off | anthropic.com/engineering/effective-harnesses-for-long-running-agents (2025-11-26) | a progress log, a JSON feature list agents may only flip, git commits, a start-up health check | **ADOPT** the pattern | one hand-off note per task costs nothing |
| Multi-agent research system | anthropic.com/engineering/multi-agent-research-system (2025-06-13) | the lead saves its plan; sub-agents store outputs and pass references back | **ADAPT** | a hand-off links to notes, it does not copy them |
| A2A protocol | a2a-protocol.org/latest/specification/ (v1.0.0) | Task with states (`INPUT_REQUIRED`, …), Artifacts, `contextId` grouping tasks | **ADAPT** | the hand-off note's state and artifact shape |
| OpenAI Agents SDK handoffs | openai.github.io/openai-agents-python/handoffs/ (undated) | a handoff is a tool inside one run; history passed or filtered | **REJECT** | in-process only |
| LangGraph store | docs.langchain.com/oss/python/langgraph/persistence (undated) | per-thread vs cross-thread memory; TTL with refresh-on-read (from search snippets, not verified) | **ADAPT** (unverified) | review dates rather than silent TTL |
| CRDTs (Automerge); grite leases | automerge.org; arxiv.org/html/2606.19616 (2026-06-17) | merge without loss but a non-Markdown format; grite: append-only log in git, TTL advisory leases (synthetic agents only) | **REJECT** CRDT, **ADAPT** leases | one-fact-per-note rarely conflicts; leases only for hub notes if needed |
| MCP authorization | modelcontextprotocol.io/specification/2025-11-25/basic/authorization | OAuth 2.1; the server validates audience; server-defined scopes, 403 `insufficient_scope`, step-up; no token passthrough; no per-tool or per-note authorization | **ADAPT** | identity and coarse scopes from the token; per-layer rights at our gateway |

Not verified by the survey: Basic Memory Teams being cloud-only (implied), Mem0's history and expiry, Letta
self-hosted git, LangGraph's TTL details, A2A's security section (only the first 100K characters read).

Sources read: docs.basicmemory.com (llms.txt; teams/members-and-roles; cloud/file-history; agents/review-runs;
concepts/schema-system), github.com/basicmachines-co/basic-memory, github.com/getzep/graphiti,
arxiv.org/abs/2501.13956, docs.mem0.ai/core-concepts/memory-types, github.com/mem0ai/mem0,
docs.letta.com (multi-agent-shared-memory; concepts/shared-memory), code.claude.com/docs/en/memory,
platform.claude.com memory-tool, anthropic.com/engineering (multi-agent-research-system;
effective-harnesses-for-long-running-agents), a2a-protocol.org/latest/specification,
openai.github.io/openai-agents-python/handoffs, docs.langchain.com/oss/python/langgraph/persistence, automerge.org,
arxiv.org/html/2606.19616, modelcontextprotocol.io/specification/2025-11-25/basic/authorization.

## Design (approved 2026-11-23)

One store (the B182 notes), one write path with identity (the governed gateway), and rules that live in code at that
gateway, not in prose.

### Context layers

| Layer | Where | Reads | Writes |
|---|---|---|---|
| **Lab rules** | `AGENTS.md`, `CLAUDE.md`, ADRs (git) | everyone | humans, through git (unchanged) |
| **Project memory** | the existing notes (top level of `~/agent-memory/weyland/`) | everyone with memory access | any human; agents: create a new note, append to one, or edit one only with the version they read (below); move or delete: humans only |
| **Task** | `task/<item>/` (a B-number or an incident id): working notes plus one `handoff.md` | everyone on the item | any participant, human or agent |
| **Person** | `person/<username>/`: that person's OWN Basic Memory server (2026-11-23: the shared server is constrained to one project, so a project name cannot keep notes private) | that person and that person's agents only, through the governed tools | the same |
| **Session** | each harness's own transcript and summary | that harness | that harness (unchanged; not in the store) |

### Identity and rights

* Every write carries an identity from a validated token, set by the gateway (anti-spoof, as today): a person
  (`X-Forwarded-User`) and a client (`X-Forwarded-Consumer`). An agent gets its own Keycloak client (`claude-code`,
  `codex`, …) instead of sharing one Bifrost key, and may act **on behalf of** its person.
* **How agents get that identity: MCP OAuth** (owner, 2026-11-23: "yes, go with A"). Each harness has a public client
  and signs its person in (authorization code + PKCE; the gateway publishes RFC 9728 metadata naming the realm), so the
  token carries the person and the harness: "agent `claude-code`, on behalf of `edward`". A second human signs in as
  themselves. Rejected: per-harness service accounts minting tokens from a stored secret (no person in the token;
  Codex has no header helper; nothing for a second human).
* Rights are a small table in the memory compositor (code, unit-tested), keyed by identity and layer. A forbidden write
  is refused with a reason naming the rule; nothing reaches Basic Memory.
* Reads stay as they are; the person layer adds one read rule (only its owner and the owner's agents).

### Provenance (stamped by the gateway, never trusted from the caller)

`created_by`, `updated_by` (`user:<name>` or `agent:<client>`, plus `on_behalf_of: user:<name>` for an agent),
`author_kind` (`human` | `agent`), `created_at`, `updated_at`, `source` (the B-number, incident or session id). A
Basic Memory schema makes them required, so a note written around the gateway shows up as non-conforming.

### Conflicts

Write classes by risk (Letta): **create** fails if the note exists; **append** always succeeds; **edit** must carry the
hash of the version the writer read and is refused if the note changed since (no silent overwrite); **rewrite, move,
delete** are for humans only. No CRDT; an advisory lease only if a hub note (`MEMORY.md`) turns out to be contested.

### Stale facts

Supersede, never delete (Graphiti): a correcting note links the old one (`superseded_by`, `invalid_at`), so history
stays searchable and agents skip invalid notes. A `review_by` date per note type; `check-shared-memory.py` lists notes
past it for a human to confirm or supersede (flag, never delete). A task layer is reviewed when its item closes: durable
lessons are promoted to project memory, the rest is archived.

### Hand-off record

`task/<item>/handoff.md`, one per item: state (`working`, `input-required`, `done`, after A2A), what was done, what was
verified (with evidence), what is open, the next step, and `[[links]]` to the notes and artifacts (links, not copies).
Linear keeps the status; the hand-off keeps the working detail.

### What it reuses from B182

The notes, Basic Memory 0.23.2 (no upgrade), `/mcp-memory` and its Keycloak identity, the compositor's
hide-and-refuse middleware, `agent-memory-watch` (gitleaks covers every layer, being the same directory), and the
fail-closed rule (unreachable is not "no memory"). New: a write path through the compositor with a secret check at
write time, which B182 could not do (Basic Memory has no hook).

### Walking skeleton (proposed)

Scenario S1/S2's riskiest part: **identity-checked, provenance-stamped writes through the governed gateway.** A write
tool on the memory compositor that reads the caller's identity from the gateway's headers, checks the rights table,
stamps provenance, enforces create-fails-if-exists and edit-needs-the-version-read, and forwards to Basic Memory.
Tests: a forbidden write is refused (another person's layer; an agent rewriting project memory); every accepted write
carries its author; a stale edit is refused. Then one live end-to-end write through `/mcp-memory` with a real token.

### Skeleton built (2026-11-23)

`services/weyland-mcp-compositor/governed_write.py` (rights, layers, provenance, write classes, secret check, audit
line), `governed_store.py` (the Basic Memory adapter: a missing note is "no note", any other error is raised, so an
unreachable store is never "no memory"), two tools in `app.py` behind `GOVERNED_WRITE=1`, on the memory compositor only.
Runbook: [shared-agent-memory.md § Governed writes](../runbooks/shared-agent-memory.md).

Before building, Basic Memory's contract was observed on the live server, not assumed: `write_note` merges a
`metadata` dict into the frontmatter and fails on an existing note unless `overwrite`; `edit_note` appends by file path;
`read_content` returns the raw file as `text`; a missing note is "Resource not found".

**Tests:** 48 (governed writes 22, the store adapter 5, manifests 2, the existing config tests), run in CI's Python
lane image. A forbidden write is refused with the rule named; every accepted write carries its author; a stale replace
is refused.

**Live run against the real store** (the compositor image on rogueone, the identity headers set as the gateway sets
them; notes in `task/b256/`): 12 of 12 behaved as designed. Two defects the fake store could not show were found and
fixed with regression tests: a replace re-wrapped Basic Memory's quoted timestamps (frontmatter is now read with
PyYAML's `BaseLoader`), and a human's edit inherited an agent's `on_behalf_of` because Basic Memory keeps frontmatter
keys a write does not name (every write now names it).

Not in the skeleton (the design's next steps): agent Keycloak clients (`claude-code`, `codex`, …) and moving today's
writers onto this path; the person layer's read rule on Basic Memory's own read tools; `review_by` and supersede
fields; the hand-off note's schema.

# Context engineering (B255) — draft

**Status: in progress (Linear EMA-356).** Measurements first, then a dated industry survey, trials on B253's task set,
and the harness and service changes that survive. Verdicts and an ADR follow when the trials are in.

## Why

Four failures with one cause, each fixed alone: the operator's 7B brain broke on the full ~95-tool fleet (B45); Lab
Recall lost its tool list to Ollama's default `num_ctx` (B250 era); B253's single agent carried ~26.7k tokens of tool
schemas a call and returned empty answers on reasoning tasks ([realm-evaluation.md](realm-evaluation.md)); and the
coding-agent harness loads into every session unmeasured.

## Measurements

### The coding-agent harness (Claude Code, this repo)

**Session 1 — 2026-11-20, a fresh session, `/context` before any message, Opus 5.5 (1M window):** 61.1k tokens (6%).

| Category | Tokens | Detail |
|---|---|---|
| System prompt | 3.0k | Claude Code's own (not ours to change) |
| System tools | 9.4k | Claude Code's built-in tools (not ours to change) |
| MCP tools | 0.7k | Deferred loading is on: 3 tools loaded, 400+ available on demand |
| MCP server instructions | 6.0k | Every connected server's instruction text (Bifrost bundle, Keploy, Figma, Jam, Linear, Context7, Serena and others) |
| Custom agents | 6.6k | Plugins 4.4k (pr-review-toolkit ~2.4k, adr ~1.5k, others); AI-DLC's 14 agents ~1.6k; tech-decision-advisor 0.7k |
| Memory files | 22.8k | `MEMORY.md` 9.2k; AI-DLC rule layers 9.4k (`org.md` 4.3k, `project.md` 2.8k, four phase files 1.6k, `team.md` 0.5k, `.claude/rules/aidlc.md` 0.2k); `AGENTS.md` 3.8k; `CLAUDE.md` 0.3k; `~/.claude/CLAUDE.md` 0.2k |
| Skills | 9.9k | AI-DLC's ~43 project skills ~2.9k; built-in skills ~2.7k; Figma plugin ~1.1k; ~150 other skills at under 20 tokens each |
| Messages | 2.6k | Session-start hook output (output styles, plugin preambles) |
| Compact buffer | 3.0k | Reserved |

**What is ours:** about 49k of the 61k. **AI-DLC alone:** about 14k (rule layers, skills, agents) in every session,
whether or not AI-DLC runs. **Largest single file:** `MEMORY.md` (9.2k, 285 notes, growing).

**How the owner works:** "I never start new sessions in this repo" (2026-11-20). Sessions are long-running and get
compacted, so the start-up load matters less than conversation growth and what survives compaction.

**Long sessions, measured mid-flight (2026-11-20).** Every assistant turn in a transcript records its request's input
tokens (fresh + cache read + cache written), which is the real context size of that request:

| Session | Requests | Context at the last request | Peak | Just before a compaction (mean) | Right after a compaction (mean) |
|---|---|---|---|---|---|
| `9e3015c4` (B249 to B255, 2026-11-19/20) | 6,081 | 579,736 (58%) | 976,683 | 972,884 (5 compactions) | 105,415 |
| `de8fed56` (to 2026-11-14) | 49,981 | 696,971 | 976,893 | 964,344 (35 compactions) | 104,815 |

Compaction fires at about 97% of the 1M window, so a long session spends most of its requests carrying several hundred
thousand tokens of history. After a compaction it restarts at about 105k: the ~61k start-up load, the ~4.4k summary and
the most recent messages.

**What the summaries keep (2026-11-20, `de8fed56`'s 35 compaction summaries, keyword check per standing rule):**

| Standing rule | Kept in the summary |
|---|---|
| Secrets never in chat; DoD before closing | 35/35 |
| Cluster read-only | 34/35 |
| The owner handles all git | 32/35 |
| Host-label rules for commands | 31/35 |
| No emojis | 26/35 |
| NodePorts, never port-forward | 19/35 |
| One question at a time | 17/35 |
| Ask before external installs | 1/35 |

Every rule here also lives in `AGENTS.md` or a memory note, which reload after each compaction, so none was lost: the
files kept them, not the summaries. A rule that lives only in a conversation has roughly even odds of surviving a
compaction. Implication: standing instructions belong in files at once, and compaction instructions should name what
to carry (open decisions, the current item's state, anything said only in conversation).

**Compaction (2026-11-20, the session transcripts under `~/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/`):**
7 sessions; 2 have compacted. The main working session (`de8fed56`, a 2.3 GB transcript) has compacted 35 times, the B249
to B255 session (`9e3015c4`) 5 times. A compaction summary averages about 4,400 tokens (characters / 4): that summary is
all the session carries forward about everything before it. Next: sample summaries against what preceded them, to see
what a summary drops (standing instructions, mid-item decisions, open threads).

### Service surfaces

To be measured from Langfuse: the operator, the Realm (B253 data: the single agent 26.7k a call, the specialists
~3.7k-3.9k a call, on a 32,768-token window), Open WebUI's Lab Recall and Lab Status presets, the tool-server RAG.

## Industry survey

To be written: each technique in EMA-356's Scope 3 with its primary source, date, and an adopt / trial / reject verdict.

## Trials

To be run on `eval_sets/realm.json` with `scripts/realm-eval.sh`.

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

**Langfuse, last 7 days (2026-11-20, `scripts/langfuse-context-tokens.sh 7`):** the free lane (`qwen2.5:7b-operator`,
`wl-local`) took 1,565 calls averaging 9,445 input tokens, 95th percentile 27,396, **largest 31,868 against a 32,768
window**: the calls nearest the ceiling were probably truncated (Ollama drops the oldest messages silently). Nearly all
of it was B253's evaluation. The judge (`gpt-oss:20b-judge`) averaged 1,181 (largest 5,349); Langfuse's online
evaluators 2,266-4,236. The operator and the tool-server RAG made no traced calls in the window (idle), and Open WebUI
is not traced, so those three are measured by replaying their real prompt and tools against Ollama instead.

**Replayed on the real model (2026-11-20):** each surface's real system prompt and tool schemas, built inside the
operator pod from the live fleet, sent to the surface's model with a 1-token answer; the count is Ollama's
`prompt_eval_count` (what the model received). Open WebUI adds a little wrapper text of its own, so its rows are lower
bounds.

| Surface | Model | Window | Tool schemas | Prompt before any conversation | Share |
|---|---|---|---|---|---|
| Operator, system prompt only | qwen2.5:7b-operator | 32,768 | 0 | 303 | 1% |
| Operator, local brain (curated) | qwen2.5:7b-operator | 32,768 | 21 | 5,850 | 18% |
| Operator, sweep brain (no Realm) | qwen2.5:7b-operator | 32,768 | 20 | 5,633 | 17% |
| Operator, full fleet (what Haiku gets) | qwen2.5:7b-operator | 32,768 | 107 | 27,742 | **85%** |
| Lab Status | qwen3:30b-a3b | 16,384 | 13 | 4,321 | 26% |
| Lab Recall | qwen2.5:7b-operator | 16,384 | 8 | 3,481 | 21% |
| Lab Recall (thorough) | qwen3:30b-a3b | 16,384 | 8 | 3,483 | 21% |

The full-fleet row is the B45 failure in numbers: 85% of the window gone before a message. **A tool result can overflow
a preset:** one `k8s_pods_list_in_namespace` for `weyland` is 15,097 tokens (37,858 characters), so "which pods are
running?" in Lab Status builds about 19,400 tokens against a 16,384 window, and Ollama silently cuts part of it. The
operator already caps each tool result for its local brain (`LOCAL_TOOL_RESULT_CAP`, 12,000 characters, about 3,000
tokens); Open WebUI's presets have no cap.

**The tool-server RAG truncates in production (measured 2026-11-20).** `/context/ask` calls `gpt-oss:20b` through
Ollama's `/v1/chat/completions` without a context size, and the stock model sets none, so it runs at Ollama's default
for rogueone, **4,096 tokens** (`ollama ps`). Replayed from inside the tool-server pod with its own retrieval, context
builder and system prompt (209 characters):

| Question | Chunks | Prompt the model received at the default window | Same prompt at a 32,768 window |
|---|---|---|---|
| Postgres backups | 5 | 2,880 | 2,880 |
| Postgres backups | 10 | **2,050** | **4,643** |
| Bifrost vs LiteLLM (a comparison: B247's 2x depth) | 10 | 2,196 | 2,196 |

At 10 chunks, the default window kept 2,050 of 4,643 tokens: more than half the retrieved context dropped with no error,
and the reasoning tokens gpt-oss writes share the same 4,096. Whether a request truncates depends on chunk size, so B247's
2x depth on comparisons and any `limit` above 5 can silently lose evidence.

## Industry survey (2026-11-20)

Primary sources, fetched 2026-11-20 by a research agent; the claims marked **checked** were re-read on the source page
by the main session. Recommendations are provisional: "trial" items are decided by the trials below, "adopt" items by
the owner, and the final verdicts go in the ADR.

| Technique | Source (date) | What it says | Applies to | Provisional call |
|---|---|---|---|---|
| Compaction timing | code.claude.com/docs/en/model-config (undated) | **checked:** 1M-window models compact at about 967K by default; `/autocompact 500k` (per model, saved), `autoCompactWindow`, `--autocompact`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`; minimum 100K | harness | trial an earlier window (e.g. 400-500K) |
| Compaction content | code.claude.com/docs/en/hooks; /costs; /context-window (undated) | **checked:** PreCompact hook stdout becomes instructions for the compaction summary; also `/compact <focus>` and a `# Compact instructions` section in CLAUDE.md; PostCompact carries the summary; SessionStart `compact` re-injects context | harness | adopt: say what a summary must keep (open items, decisions, IDs, conversation-only instructions), and log the summaries |
| What survives compaction | code.claude.com/docs/en/context-window (undated) | project CLAUDE.md, unscoped rules, auto memory and skill descriptions reload from disk; path-scoped rules and nested CLAUDE.md do not until touched | harness | design constraint: standing rules live in files that reload |
| Long-task progress files | anthropic.com/engineering/effective-harnesses-for-long-running-agents (2025-11-26) | compaction alone is not sufficient; keep a progress file and a JSON task list, commit after each change | harness, services | adopt for long items |
| Context editing (clear stale tool results) | platform.claude.com/docs/en/build-with-claude/context-editing (undated); LangChain `ContextEditingMiddleware` | replace old tool results with a placeholder past a threshold; "safest, lightest touch" (Anthropic, 2025-09-29) | services (7B, 32K) | trial on the operator and the Realm |
| Tool search / deferred loading | platform.claude.com/.../tool-search-tool; anthropic.com/engineering/advanced-tool-use (2025-11-24) | ~85% fewer definition tokens; tool choice degrades past 30-50 tools; MCP eval accuracy up (Opus 4: 49% to 74%) | harness (already on), services | already adopted in Claude Code |
| Tool retrieval for LangGraph | github.com/langchain-ai/langgraph-bigtool; RAG-MCP arXiv 2505.03275 (2025-05-06) | retrieve a few tools per step from embedded descriptions; RAG-MCP: tool-selection accuracy 43.13% vs 13.62%, prompt tokens down over 50% | services | trial on the Realm's single agent (B253 task set) |
| MCP code mode | anthropic.com/engineering/code-execution-with-mcp (2025-11-04); blog.cloudflare.com/code-mode (2025-09-26); docs.getbifrost.ai/mcp/code-mode | tools called from code instead of many schemas; Anthropic: ~150K to ~2K tokens on one workflow; Bifrost (vendor): input tokens down 58-93% at 96-508 tools; no evidence for 7B models | services | trial cautiously; not for the harness (tool search covers it) |
| Sub-agents for reading-heavy work | anthropic.com/engineering/multi-agent-research-system (2025-06-13) | isolate heavy reading, return 1-2K summaries; multi-agent uses ~15x the tokens of chat; poor fit for tightly coupled work | harness | adopt selectively (already used) |
| Just-in-time retrieval | anthropic.com/engineering/effective-context-engineering-for-ai-agents (2025-09-29) | keep identifiers, load content when needed; hybrid with a small pre-loaded core | both | adopt: move detail out of always-loaded files |
| Lean rule files, skills progressive disclosure | code.claude.com/docs/en/memory; /skills (undated) | **checked:** auto memory loads only the first 200 lines or 25KB; CLAUDE.md "target under 200 lines"; `@imports` do not reduce cost; skill listing budget is 1% of the window, least-used descriptions dropped past it | harness | adopt: cap `MEMORY.md` (now 18.9KB, 76% of the cap); scope or defer always-loaded rule files |
| Context rot | trychroma.com/research/context-rot (2025-07-14); NoLiMa arXiv 2502.05167; RULER arXiv 2404.06654 | quality falls as context grows: NoLiMa 11 of 13 models below half their short-context score at 32K; RULER only half of models held at 32K | both | design constraint: small, focused contexts |
| Truncation detection (Ollama) | docs.ollama.com/context-length; Ollama source `server/prompt.go` (2026-11-18) | over-long chats drop the oldest messages, logged only at DEBUG; detect via `prompt_eval_count` near `num_ctx`, or send `truncate:false` for a hard error | services | adopt the guard (Scope 6) |

**Already true in the harness:** MCP tool schemas are deferred (0.7K of 61.1K). **Most direct lessons for how the owner
works:** compaction fires late (~967K) and is steered by nothing today; each summary is ~4.4K; files, not summaries,
carry the standing rules.

## Changes applied

| Date | Change | Approved | Token cost | How it is judged |
|---|---|---|---|---|
| 2026-11-20 | `# Compact instructions` section in the root `CLAUDE.md`: keep the active item and its state, owner decisions verbatim, conversation-only instructions, identifiers in use, open threads; drop raw tool output | owner: "yes, add the compact instructions" | `CLAUDE.md` 588 to 1,638 bytes (about +260 tokens, every session) | the next compaction summaries against the 35-summary baseline above (standing rules kept, active item and next step present) |
| 2026-11-20 | RAG endpoints on `gpt-oss:20b-rag` (8K window, `nodes/rogueone/ollama/gpt-oss-20b-rag.Modelfile`): the tool-server's `/context/ask` and weyland-agent; hidden in Open WebUI | owner: "yes, fix it" | none in the prompt; 9.7 of 13.1 GiB on the GPU (same as the 8K judge variant); shares one loaded copy with `gpt-oss:20b-judge` | replay: the 10-chunk prompt now arrives whole (4,643 of 4,643; it was 2,050 at the 4,096 default) |

## Trials

To be run on `eval_sets/realm.json` with `scripts/realm-eval.sh`.

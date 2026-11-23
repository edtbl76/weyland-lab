# Context engineering (B255)

**Status: DONE 2026-11-22, [ADR-0017](../adr/0017-context-engineering-for-the-harness-and-services.md) accepted (Linear
EMA-356).** Measurements first, then a dated industry survey, trials on B253's task set, and the harness and service
changes that survive.

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

**Confirmed in production, 2026-11-20 21:59:** a real `/context/ask` (limit 10) on the old setup made Ollama log
`level=WARN msg="truncating input prompt" limit=2050 prompt=4643 keep=4 new=2050` (rogueone `journalctl -u ollama`),
while the same request's closing line still read `truncated = 0`. **For the guard:** the WARN line is the reliable signal;
the `truncated` flag on the closing line is not.

**After the fix (2026-11-20 22:03, both services on `gpt-oss:20b-rag`):** the same real ask arrived whole
(`n_ctx_slot = 8192, task.n_tokens = 4643`, no warning). **A second gap surfaced:** at 22:02:59 Ollama truncated a
10,596-token prompt to 4,098 on the same loaded model; the front door's access log (`docker logs ollama-proxy`) shows the
caller was LiteLLM on timberback (`litellm/1.93.0`, `/api/chat`), i.e. `wl-judge-oss`: a Langfuse online evaluator
scoring the 10-chunk test trace (question + 10 chunks + answer). The judge variant is capped at 8K by the GPU (16K does
not fit), so evaluator scores on large RAG traces are judged on a cut prompt. Open for B255: trim what the evaluators
receive, or a slower 16K judge.

## Industry survey (2026-11-20)

Primary sources, fetched 2026-11-20 by a research agent; the claims marked **checked** were re-read on the source page
by the main session. Recommendations are provisional: "trial" items are decided by the trials below, "adopt" items by
the owner, and the final verdicts go in the ADR.

| Technique | Source (date) | What it says | Applies to | Provisional call |
|---|---|---|---|---|
| Compaction timing | code.claude.com/docs/en/model-config (undated) | **checked:** 1M-window models compact at about 967K by default; `/autocompact 500k` (per model, saved), `autoCompactWindow`, `--autocompact`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`; minimum 100K | harness | adopted 2026-11-22: 500K for this repo (Changes applied) |
| Compaction content | code.claude.com/docs/en/hooks; /costs; /context-window (undated) | **checked:** PreCompact hook stdout becomes instructions for the compaction summary; also `/compact <focus>` and a `# Compact instructions` section in CLAUDE.md; PostCompact carries the summary; SessionStart `compact` re-injects context | harness | adopt: say what a summary must keep (open items, decisions, IDs, conversation-only instructions), and log the summaries |
| What survives compaction | code.claude.com/docs/en/context-window (undated) | project CLAUDE.md, unscoped rules, auto memory and skill descriptions reload from disk; path-scoped rules and nested CLAUDE.md do not until touched | harness | design constraint: standing rules live in files that reload |
| Long-task progress files | anthropic.com/engineering/effective-harnesses-for-long-running-agents (2025-11-26) | compaction alone is not sufficient; keep a progress file and a JSON task list, commit after each change | harness, services | covered: backlog, Linear, memory and compact instructions (Verdicts) |
| Context editing (clear stale tool results) | platform.claude.com/docs/en/build-with-claude/context-editing (undated); LangChain `ContextEditingMiddleware` | replace old tool results with a placeholder past a threshold; "safest, lightest touch" (Anthropic, 2025-09-29) | services (7B, 32K) | trial on the operator and the Realm |
| Tool search / deferred loading | platform.claude.com/.../tool-search-tool; anthropic.com/engineering/advanced-tool-use (2025-11-24) | ~85% fewer definition tokens; tool choice degrades past 30-50 tools; MCP eval accuracy up (Opus 4: 49% to 74%) | harness (already on), services | already adopted in Claude Code |
| Tool retrieval for LangGraph | github.com/langchain-ai/langgraph-bigtool; RAG-MCP arXiv 2505.03275 (2025-05-06) | retrieve a few tools per step from embedded descriptions; RAG-MCP: tool-selection accuracy 43.13% vs 13.62%, prompt tokens down over 50% | services | trial on the Realm's single agent (B253 task set) |
| MCP code mode | anthropic.com/engineering/code-execution-with-mcp (2025-11-04); blog.cloudflare.com/code-mode (2025-09-26); docs.getbifrost.ai/mcp/code-mode | tools called from code instead of many schemas; Anthropic: ~150K to ~2K tokens on one workflow; Bifrost (vendor): input tokens down 58-93% at 96-508 tools; no evidence for 7B models | services | not trialed (see Verdicts); not for the harness (tool search covers it) |
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
| 2026-11-20 | Two-tier memory index: `MEMORY.md` = working rules and starred notes (the always-loaded core), `MEMORY-catalog.md` = every note by topic (read on demand); `check-shared-memory.py` checks both (core within 12 KB, every note linked, no dangling link) in every mode, the 15-min watchdog included; `AGENTS.md` and the runbook updated | owner: "yes, split it" | `MEMORY.md` 19,056 to 11,666 bytes (about -1,850 tokens every session; it was at 76% of Claude Code's 25 KB load cap) | the check passes on the real store (287 notes); it caught one dangling link at the split |
| 2026-11-20 | AI-DLC's ambient import trimmed to `team.md` and `project.md` (`.claude/rules/aidlc.md`): `org.md` and the four phase files no longer load into every session; `/aidlc` runs still receive all seven from the engine (`rules_content`) | owner: "sure" | about -5.9k tokens every session (the 9.4k of AI-DLC rule files becomes ~3.5k) | `/aidlc --doctor` 47/47 after the change; the next `/context` shows the memory-files total |
| 2026-11-20 | MCP servers off for this repo only: `serena`, direct `context7`, Figma (`.claude/settings.local.json`); `keploy` and the claude.ai Jam connector via `/mcp`; recorded in `docs/runbooks/coding-agents.md` and the memory note `mcp-servers-off-in-weyland`, so a missing tool is re-enabled, not worked around | owner: "ok, turn them off and record it" | part of the ~6k of MCP server instructions plus Figma's ~1.1k of skill descriptions | the next `/context` |
| 2026-11-20 | Truncation guard: `ollama-truncation-watch` (rogueone user timer, every 15 min, `scripts/ollama_truncation_watch.py`) reads Ollama's journal for `truncating input prompt` WARN lines and pushes to the Kuma push monitor `ollama-truncation` (any hit or an unreadable journal is DOWN; Telegram on alert) | acceptance criterion (Scope 6) | none in any prompt | 6 tests; a real dry run over 2 h found the day's 6 truncations (worst 10,596 sent, 4,098 kept); first live run pushed UP; `kuma_push_check.py` OK (7 monitors) |
| 2026-11-20 | Harness budget guard: `scripts/check-harness-budget.py` in CI's repo-guards step measures what every session loads (CLAUDE.md and its @-imports, unscoped `.claude/rules/`, HTML comments stripped as Claude Code does, plus project skill and agent descriptions) against budgets of today's size + ~15% | acceptance criterion (Scope 6) | none | 7 tests; on the repo: instructions 20,124/26,000 bytes (5 files), skills 15,043/17,500, agents 3,971/5,000 |
| 2026-11-20 | Lab Status and Lab Recall (thorough) at a 32K window (`open_webui_curate.py` `LARGE_CTX`; both run `qwen3:30b-a3b`, so they share one loaded copy) | owner: "yes, raise the status window" | none in the prompt; a heavy question takes ~50 s instead of ~24 s; 20.6 GiB, 9.7 on the GPU | replay: "which pods are running?" reached the model as 8,194 of 19,428 tokens at 16K, whole at 32K |
| 2026-11-20 | Evaluator inputs trimmed: the tool-server and weyland-agent record `{query, context}` as `rag-generate` metadata; `langfuse_evaluators.py` maps each rule to only what it needs (Hallucination keeps the whole Input) and PATCHes drifted rules; weyland-agent got its first tests | owner: "yes, trim the evaluators" | judge prompts carry the chunks once (rules using both variables carried them twice; the cut prompt was 10,596 tokens) | tests: tool-server 96, agent 1, Dagster suite 423 (whole suite, CI order); **live, 2026-11-21:** after a 10-chunk ask, 0 truncation warnings and the largest prompt 6,466 tokens (8,192 window), against 10,208-10,596-token evaluator prompts cut before. The first rollout's reconcile timed out on one PATCH and stopped, leaving 6 rules on the old mapping (2 prompts cut); a rerun finished it, and the script now keeps going past one slow call and exits 1 on a partial reconcile |
| 2026-11-20 | weyland-agent joined CI (`scripts/ci/images.tsv`; it ran a hand-tagged `v20` that never picked up source changes, so the evaluator-metadata change could not ship), with a ship transaction `txn_agent` (`/ready` + one real `/agent/ask`) | owner: "yes, add weyland-agent to CI" | none | local image build and app import OK; `txn_agent` against the live agent `TXN_OK` in 27 s; bats 1,392/1,401 (only promtool) |
| 2026-11-22 | Auto-compaction on at a 500k window for this repo (`.claude/settings.json`: `autoCompactEnabled: true`, `autoCompactWindow: 500000`). The owner's user settings had auto-compaction off, so sessions ran to the limit or a manual `/compact`; project settings override that here only. Runbook: coding-agents.md § Auto-compaction at 500k | owner: "yes, set it to 500k", "yes, turn it on for this repo" | requests carry at most ~500k of history instead of up to ~967k; about twice as many compactions | the next summaries keep the active item, decisions and open threads (the keyword check in § The coding-agent harness) |

## Trials

Run on B253's 33 tasks (`eval_sets/realm.json`) with `scripts/realm-eval.sh`, same free lane, same blind judge, 3 reps.
The `single` arm is rerun alongside, so each trial is compared with a same-day control, not with B253's numbers.
Results: `eval/context-b255/`. Runbook: [realm-of-agents.md § Context-engineering trials](../runbooks/realm-of-agents.md).

**Why these two.** In B253 the single agent carried all 99 tools (~26k tokens of schemas) on every call in a 32K
window, and called no tool at all in 35 of 93 runs. 20 of its 93 runs made 3 or more tool calls, so context editing
has fewer runs to act on than retrieval.

| Arm | Technique | Settings |
|---|---|---|
| `single-rt` | tool retrieval (langgraph-bigtool, RAG-MCP) | top 8 of 99 by BM25 over name, the first 400 characters of the description, and the family's roster text; stopwords dropped. Lexical because the Realm has no embedding model. Offline check against the live tools: the top 8 include a family a correct agent would use for 18 of the 19 tool tasks (precision 0.48) |
| `single-ce` | context editing (Anthropic; LangChain `ClearToolUsesEdit`) | past 4k tokens of messages, all but the newest 2 tool results become `[cleared]` in the model's view; 4k because ~26k of schemas leave ~6k of a 32K window |

### Results (2026-11-22, image `git-e05a1471`)

297 runs (33 tasks x 3 arms x 3 reps), 285 judged by `wl-judge-oss`, blind to the arm. A failed run scores 0.

| Arm | Failures | Rubric met (mean ± sd) | Single-realm | Multi-realm | Judge 1-5 | Input + output tokens a run | Seconds a run | Tool calls |
|---|---|---|---|---|---|---|---|---|
| single (control) | 6 | 0.34 ± 0.34 | 0.37 | 0.28 | 2.04 | 60,507 | 15 | 1.3 |
| single-ce | 6 | 0.37 ± 0.34 | 0.45 | 0.23 | 2.18 | 56,550 | 17 | 1.2 |
| single-rt | 0 | 0.39 ± 0.35 | 0.51 | 0.20 | 2.11 | **9,705** | 21 | 2.2 |

Paired by task (mean of 3 reps per task, bootstrap 95% CI, 5,000 resamples):

| Comparison | Tasks | Difference | 95% CI | Wins / ties / losses |
|---|---|---|---|---|
| single-ce minus single, all | 33 | +0.03 | −0.04 to +0.10 | 11 / 14 / 8 |
| single-rt minus single, all | 33 | +0.05 | −0.05 to +0.17 | 11 / 11 / 11 |
| single-rt minus single, single-realm | 20 | +0.14 | −0.00 to +0.30 | 9 / 7 / 4 |
| single-rt minus single, multi-realm | 13 | **−0.09** | **−0.16 to −0.01** | 2 / 4 / 7 |
| single-rt minus single, tasks needing tools | 19 | −0.04 | −0.12 to +0.05 | 5 / 6 / 8 |
| single-rt minus single, tasks needing none | 14 | +0.17 | −0.01 to +0.38 | 6 / 5 / 3 |

Findings:
1. **Context editing never fired.** None of its 93 successful runs cleared anything: the longest runs reach about
   27.6k input tokens a call, about 26.5k of them tool schemas, so the messages (tool results included) peak around
   1-2k tokens, under the 4k trigger. This lab's tools return small results; the schemas are the cost. Because the arm
   behaved exactly like the control, its +0.03 (CI −0.04 to +0.10) is a measured **noise floor** for this setup.
2. **Retrieval cuts the context by 84%** (60.5k to 9.7k tokens a run) and removes every failure. The 6 control failures
   are two reasoning tasks (`v-simplify`, `w-faithfulness`) where the agent holding 99 schemas returned an empty answer
   in every rep; with 8 tools it answered (+1.00 on each). Without those two tasks, retrieval's overall difference is
   about zero.
3. **A fixed top 8 starves multi-realm tasks** (−0.09, the only CI that excludes zero): tasks spanning several tool
   families lose the specific tools they need (`x-alerts-coverage-score` retrieved 1 tool; `x-restarts-postmortem`
   kept the families but not the right k8s tools). On single-realm tasks retrieval leans positive (+0.14, CI touching
   zero). Retrieval is also 6 seconds slower a run, because the agent calls more tools (2.2 against 1.3).
4. Offline family recall (18 of 19) overstated retrieval's usefulness: having a tool from the right family in the
   set is not the same as having the tool the task needs.

First-day reading (2026-11-21), revised by the replicate below: context editing has nothing to clear here, and static
retrieval seemed to starve multi-family tasks, which led to the per-step trial. The final verdicts are under
[Verdicts (for the ADR)](#verdicts-for-the-adr).

### Per-step retrieval (arm `single-rs`, owner: "yes, run the per-step retrieval trial", 2026-11-22)

The agent starts with the same top 8 as `single-rt`, plus a `find_tools(need)` tool. Each call adds up to 5 tools
matching the need (the same BM25 ranking, excluding tools it already holds), and the model is re-bound to the grown
set before its next call, so it pays only for the tools it holds; the tool node can run all 99. Run against a same-day
`single` and `single-rt` (image `git-d17b6cb9`; results `eval/context-b255-rs/`, 297 runs, 289 judged).

| Arm | Failures | Rubric met | Multi-realm | Judge 1-5 | Tokens a run | Seconds a run |
|---|---|---|---|---|---|---|
| single (control) | 7 | 0.39 ± 0.35 | 0.26 | 2.23 | 72,413 | 29 |
| single-rt | 0 | 0.37 ± 0.34 | 0.23 | 2.06 | 9,591 | 19 |
| single-rs | 1 (a timeout) | 0.35 ± 0.33 | 0.26 | 1.96 | 11,143 | 28 |

| Comparison (paired by task) | Difference | 95% CI | W / T / L |
|---|---|---|---|
| single-rs minus single-rt, all | −0.02 | −0.08 to +0.03 | 9 / 13 / 11 |
| single-rs minus single-rt, multi-realm | +0.03 | −0.04 to +0.09 | 6 / 4 / 3 |
| single-rt minus single, all (this run) | −0.02 | −0.13 to +0.10 | 10 / 9 / 14 |
| single-rt minus single, multi-realm (this run) | −0.03 | −0.12 to +0.05 | 4 / 3 / 6 |

**Per-step retrieval adds nothing on this model.** The 7B called `find_tools` in 13 of 98 runs (6 of 38 multi-realm
runs): it rarely notices that it lacks a tool, so the escape hatch goes unused. It costs 9 more seconds a run than
static retrieval for no gain.

**Both days pooled** (6 reps per task, `single-rt` minus `single`): all tasks +0.01 (CI −0.07 to +0.13); single-realm
+0.06 (−0.07 to +0.23); multi-realm −0.06 (−0.12 to +0.00); tool tasks −0.05 (−0.12 to +0.02); no-tool tasks +0.10
(−0.08 to +0.33). Tokens a run 66,427 against 9,647 (−85%). Failures 13 against 0: the 99-schema agent returns an empty
answer on `v-simplify` and `w-faithfulness` in every rep, and once on `m-operator-tables`. The first day's multi-realm
loss (−0.09) halved on the replicate: part of it was noise, and what remains is small and borderline.

### Verdicts (for the ADR)
* **Static tool retrieval (top 8): adopt** for any free-lane agent that would otherwise hold the full tool set (the
  single generalist ADR-0016 points at). Same quality, 85% fewer tokens, and no empty-answer failures. Its one cost is a
  small, borderline loss on tasks spanning several tool families.
* **Per-step retrieval (`find_tools`): don't adopt on the free lane.** The small model rarely uses it. Retest only on a
  stronger model (the paid lane), where asking for a tool is more likely.
* **Context editing: don't adopt** for the Realm or the operator: nothing to clear (tool results stay small; schemas
  are the cost).
* **Bifrost code mode: not trialed, don't adopt for now** (owner, 2026-11-22: "yes, record code mode as not trialed").
  Code mode replaces tool schemas with a code-execution interface: the model lists tool files, reads them, and writes
  code that calls them. Three things argue against spending a trial on it here. The free-lane 7B called the one
  meta-tool it was given (`find_tools`) in only 13 of 98 runs, and code mode asks more of it: several steps and
  correct code. Static retrieval already removes 85% of the context, the share code mode's published gains target
  (Anthropic ~150K to ~2K on one workflow; Bifrost, a vendor figure, 58-93% at 96-508 tools; none on a 7B model). And a
  trial needs a Bifrost configuration change. In the harness, Claude Code's tool search already covers it. Revisit for
  a strong model holding hundreds of tools.
* **AI-DLC skill and agent descriptions: leave as they are** (owner, 2026-11-22: "yes"). About 4.5k tokens a session,
  under 1% of the 500k compaction window. Trimming means editing AI-DLC's own files (held at 2.6.18; an upgrade
  overwrites them and `/aidlc --doctor` checks them) or hiding skills from model invocation; neither pays for 4.5k.
  `check-harness-budget.py` keeps them from growing unnoticed.
* **Long-task progress files: covered, no separate file** (owner, 2026-11-22: "yes"). The state Anthropic's article
  keeps in a progress file and a JSON task list already lives in things that survive compaction: the backlog and
  Linear (item, acceptance criteria, status), the shared memory store (durable lessons), and the `# Compact
  instructions` (active item, owner decisions, open threads in every summary). A per-item file would be a fourth copy
  that drifts.

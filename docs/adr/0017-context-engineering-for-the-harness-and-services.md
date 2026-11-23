# Context engineering for the coding-agent harness and the AI services

## Status

proposed

Date: 2026-11-22

## Context and Problem Statement

B255 measured what fills the context of every AI surface in the lab and of the Claude Code harness, surveyed industry
practice from primary sources, and trialed the techniques that could not be settled by reading.

What the measurements found:
* **Harness:** a fresh session started at about 61k tokens, ~49k of it ours. The long sessions here never restart, and
  with auto-compaction off in the owner's user settings they ran to ~967k or a manual `/compact`.
* **Services:** Ollama's default 4,096-token window silently truncated RAG prompts (a 10-chunk prompt kept 2,050 of
  4,643 tokens), Lab Status (8,194 of 19,428), and the Langfuse judge's evaluator prompts (10.2-10.6k cut to 8K).
* **Agent tool loops:** the Realm's single generalist carried 99 tools (~26k tokens of schemas) on every call in a
  32K window, and returned empty answers on pure-reasoning tasks.

Which techniques should the lab adopt, where, and which should it reject?

## Decision Drivers

* Measure first; trial on a fixed task set (B253's 33 tasks, blind judge) where reading cannot settle it.
* A silent truncation is a failure: fail closed and alert.
* $0 budget; no new dependency without a measured gain.
* Standing rules must survive compaction, so they live in files that reload.

## Considered Options

* Compaction: keep the default (~967k, or manual) / compact earlier (500k) / steer the summary (`# Compact instructions`).
* Ollama windows: raise the server default / a Modelfile variant per caller that needs more.
* Tool selection for a free-lane agent: all tools / static retrieval (top 8 by BM25) / per-step retrieval
  (`find_tools`, langgraph-bigtool's pattern) / MCP code mode (Bifrost).
* Context editing (clearing stale tool results, LangChain `ClearToolUsesEdit` semantics): adopt / don't.
* Always-loaded harness text: leave it / trim it and hold it to a budget.
* AI-DLC skill and agent descriptions: trim / leave.
* Long-task progress files: add per item / rely on what already survives compaction.

## Decision Outcome

Chosen, with the owner's approval of each harness change (quoted in the concept doc's Changes applied table):

**Adopt**
* `# Compact instructions` in the root `CLAUDE.md` (what every summary keeps) and **auto-compaction on at 500k for this
  repo** (`.claude/settings.json`; owner: "yes, set it to 500k", "yes, turn it on for this repo").
* **A Modelfile variant per Ollama caller that needs a larger window** (`gpt-oss:20b-rag` at 8K for RAG; 32K for Lab
  Status and Lab Recall thorough), never a larger server default: two windows on the same weights load two copies.
* **The Ollama truncation guard** (`ollama-truncation-watch`, Kuma push monitor) and the **harness budget guard**
  (`check-harness-budget.py` in CI), plus the two-tier memory index with its 12 KB core budget.
* **Evaluator inputs from generation metadata** (each Langfuse rule reads only the question or context it needs).
* **Static tool retrieval (top 8 by BM25 over name, description start and family roster text)** for any free-lane
  agent that would otherwise hold the full tool set. Pooled over 6 reps per task: quality level (+0.01, CI −0.07 to
  +0.13), 85% fewer tokens (66,427 to 9,647 a run), failures 13 to 0. Cost: a small, borderline loss on multi-realm
  tasks (−0.06, CI −0.12 to +0.00).

**Don't adopt**
* **Per-step retrieval** on the free lane: the 7B called `find_tools` in 13 of 98 runs; no gain over static retrieval
  (−0.02, CI −0.08 to +0.03).
* **Context editing** for the Realm or the operator: it never fired in 93 runs (messages peak at 1-2k tokens; the
  schemas are the cost). Its arm doubled as a measured noise floor (+0.03, CI −0.04 to +0.10).
* **Bifrost code mode**: not trialed (owner: "yes, record code mode as not trialed"); the small model rarely used a
  single meta-tool, static retrieval already removes the share code mode targets, and a trial needs a Bifrost change.
* **Trimming AI-DLC's descriptions** (~4.5k tokens; upstream files at the pinned 2.6.18) and **per-item progress
  files** (the backlog, Linear, memory and the compact instructions already carry that state).

### Consequences

* Good, because the services no longer cut prompts silently, and a new truncation alerts within 15 minutes.
* Good, because the harness's always-loaded text and memory index cannot grow unnoticed, and requests carry at most
  ~500k of history.
* Good, because the trial arms stay in the Realm (`/eval/run`, arms `single-rt`, `single-ce`, `single-rs`), so a
  model change can be re-measured with one command.
* Bad, because compaction now runs about twice as often; each one is a summary that could drop detail (checked against
  the standing rules after the next few).
* Neutral: static retrieval is not yet wired into a production path; it applies when the free-lane generalist ADR-0016
  points at is built, or to any agent given the full tool set.

**Revisit when:** the free lane's model changes (re-run the arms), a stronger model holds hundreds of tools (per-step
retrieval, code mode), or a surface starts returning large tool results (context editing).

## More Information

* Evidence: [docs/concepts/context-engineering.md](../concepts/context-engineering.md) (measurements, survey, changes
  applied, trials, verdicts). Trial results: `eval/context-b255/`, `eval/context-b255-rs/`.
* Runbooks: [realm-of-agents.md § Context-engineering trials](../runbooks/realm-of-agents.md),
  [coding-agents.md](../runbooks/coding-agents.md) (MCP servers off, always-loaded budget, auto-compaction),
  [model-serving-ollama.md](../runbooks/model-serving-ollama.md) (truncation watch, window variants).
* Backlog B255 (Linear EMA-356). Builds on [ADR-0016](./0016-simplify-the-realm-on-the-free-lane.md); follow-up B256
  (shared context for many humans and agents).

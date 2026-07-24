# Demo — Operator brain bake-off (B66)

The decision evidence for **which brain drives the B66 operator agent**: Claude (via the Max subscription's headless
`claude -p`) vs local Ollama models, measured on the operator's *actual* core skill — **agentic tool-use over the
tool-server's tools**, not generic chat. Two levels, two scripts (both stdlib-only, run on **rogueone**):

| script | measures |
|---|---|
| `scripts/brain-bakeoff/tool-selection.py` | single-shot **tool selection** — given an ops request + the tool catalog, pick the ONE right tool with correct args. Scores correct/8 + latency. |
| `scripts/brain-bakeoff/full-loop.py` | the **full agent loop** — reason → call the *live* tool-server → read the JSON → chain if the request has a condition → answer grounded in the result. Prints transcripts. |

**Why it matters:** the whole B66 "give it a Claude brain" thesis rested on *"local brains are too weak."* This
bake-off tests that premise directly. **Read-only** — the full-loop harness uses only `status`/`context_search`/
`context_ask`; the act tools (`pipeline_trigger`, `evals_*`) are deliberately excluded so nothing fires. (An act-path
bake-off, where a wrong call has consequences, is a separate careful test — TODO.)

## Prerequisites
- **rogueone** — Claude Code + the Max subscription (for `claude -p`); Ollama with the candidate models pulled.
- Tool-server live at `192.168.1.243:30080` (for the full loop). Ollama up (both for the local brains AND the
  tool-server's own `context_ask` generation).
- Each brain uses its **native protocol** (fair): Haiku emits the call as JSON-in-text; local models use native
  OpenAI `tool_calls` (the `tools` param) — which is how gpt-oss actually works and how a real framework (the
  LangGraph in `weyland-agent`) drives them.

## CLI walkthrough

List the local candidates on the box:
```
[rogueone] curl -s http://192.168.1.243:30080/models | python -c "import sys,json; print([m for m in json.load(sys.stdin)['available']])"
```

**Pre-filter — tool-calling is a HARD requirement.** A local model with no `tools` capability can't drive the operator
at all: Ollama 400s the `tools` param. That's exactly why `deepseek-coder-v2:16b` scored 0/8 — `ollama show` lists only
`completion`/`insert`, no `tools`. Screen each candidate in one line before wasting a bake-off slot on it:
```
[rogueone] ollama show <model> | grep -iA6 capabilit    # must list `tools`; if it only shows completion/insert, skip it
```

**Tool selection — across all models** (Haiku via the subscription + every local model):
```
[rogueone] python ~/IdeaProjects/weyland/scripts/brain-bakeoff/tool-selection.py gpt-oss:20b qwen3-coder:30b mistral-small3.2:24b deepseek-coder-v2:16b
```

**Full loop — across all models** (several minutes; `context_ask` calls the tool-server LLM ~1 min each):
```
[rogueone] python ~/IdeaProjects/weyland/scripts/brain-bakeoff/full-loop.py gpt-oss:20b qwen3-coder:30b mistral-small3.2:24b deepseek-coder-v2:16b
```

Env knobs: `HAIKU_MODEL` (default `haiku` — set `sonnet` to test a bigger Claude tier), `OLLAMA_BASE_URL`, `TOOLSERVER`.

## Expected result (findings so far — 2026-07-23)

**Tool selection (8 cases)** — run, confirmed:
- **Haiku 8/8** · **gpt-oss:20b 8/8** (and *faster* here) · **qwen3-coder:30b 7/8** (one `context_ask`→`context_search`
  ambiguity, not a hallucination). Local **ties** Claude on tool-selection.

**Full loop (3 tasks) — full matrix run 2026-07-23:**

| brain | score | how it did |
|---|---|---|
| Haiku | 3/3 | flawless — self-corrected the weak retrieval (re-queried), grounded, nailed the conditional chain |
| **gpt-oss:20b** | **3/3** | **tied Haiku** — re-searched on a weak hit, accurately grounded in the real KB (correctly described `weyland-guard`), fastest (5–30s) |
| qwen3-coder:30b | 3/3 | completes all + **honest-negative** on task 2; weaker synthesis on task 3 (dumped a tool list) |
| mistral-small3.2:24b | 1/3 | **malformed args** (invented `backend:"openai"` → 400), gave up on the error, skipped grounding |
| deepseek-coder-v2:16b | 0/3 | HTTP 400 every call — **broken** native tool-calling |

**Decision (B66 brain):** the "local is too weak" premise is **overturned** — `gpt-oss:20b` matched Haiku 3/3, faster,
$0, on-LAN. But "local" is NOT uniform (gpt-oss ≫ qwen ≫ mistral ≫ deepseek), so the brain is **`gpt-oss:20b`
specifically** (also the tool-server's default). **Operator brain = `gpt-oss:20b`**; **Haiku (API, cents/mo) = documented
fallback** for cloud-offload / always-up / the autonomous B45 path. ⚠️ This test was **READ-ONLY** — the **act-path**
bake-off (does a local brain misfire when triggering real pipelines/evals? mistral's malformed arg is the warning) is
a required separate test before a local brain gets `/mcp-act`.

**Act-path (dry-run, `scripts/brain-bakeoff/act-selection.py`) — run 2026-07-23:** captures each brain's *intended*
act-tool call and scores it; it **never executes**, so nothing fires. Tests correct act-tool + valid `job_name` + trap
handling (a read-that-sounds-active, ambiguous "run it", destructive "delete all eval data", unknown pipeline).
- **Haiku 8/8 · gpt-oss:20b 8/8 (tied) · mistral-small 8/8 · qwen3-coder 6/8** (both misses picked a READ tool — erred
  *safe*, never mis-fired an act) **· deepseek-coder-v2 0/8** (broken).
- **gpt-oss:20b declined all four traps** (incl. destructive + unknown-job) and never hallucinated a `job_name` → **CLEARED
  for `/mcp-act`.**
- **Defense-in-depth regardless of brain** (LLM tool-use is never 100%): the tool-server already validates `job_name`
  against defined jobs (a bad job 400s, doesn't fire), and the operator should add a **confirm step** for expensive/
  irreversible acts.

## Cleanup / teardown
Read-only — no side effects (the full loop touches only read tools; nothing is created or triggered). Nothing to tear
down.

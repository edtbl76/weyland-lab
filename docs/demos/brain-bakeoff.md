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

**Full loop (3 tasks)** — Haiku confirmed; all-models run is the completing validation:
- **Haiku 3/3, flawless** — incl. the **multi-step conditional** (task 3: `status` → check pgvector → `context_ask` →
  grounded reply) and **honest-negative** handling (task 2: the KB had nothing on guardrails, and Haiku *said so*
  rather than hallucinating — the operator-safety tell).
- **gpt-oss:20b** uses **native OpenAI tool-calling** (structured `tool_calls` + a `reasoning` field), reasoning
  correctly through the steps — the harness now reads that protocol. Run the command above across all models to score
  each on the chain + honest-negative + grounding.

**Takeaway:** the "local is too weak" premise is **stale** — local is viable for the operator's tool-use, so the brain
choice collapses to a priorities call: **local** ($0, on-LAN, but eats rogueone's GPU) vs **Haiku** (cents/month,
clean-ToS, cloud). See B66.

## Cleanup / teardown
Read-only — no side effects (the full loop touches only read tools; nothing is created or triggered). Nothing to tear
down.

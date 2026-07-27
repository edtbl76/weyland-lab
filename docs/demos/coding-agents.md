# Demo — Coding Agents (B15)

Four terminal AI coding agents (**opencode / Cline / Pi / Codex**) driving a real task at **`$0`** — write a function +
a pytest and run it — proven in-hand across free hosted providers and your ChatGPT subscription. No local model, no paid
API: local 16GB models can't drive tools and the MLflow gateway can't carry an agentic loop, so agents point **direct**
at the provider. Built + validated 2026-07-27.

Grounded in [runbooks/coding-agents.md](../runbooks/coding-agents.md), `~/.config/opencode/opencode.json`,
`~/.pi/agent/models.json`, `scripts/.env`.

## The drivers (all `$0`)

| Driver | How | Note |
|---|---|---|
| **ChatGPT sub → GPT-5.5** ⭐ | Cline / Codex → "Sign in with ChatGPT" | best — frontier model, sub-*included* usage, not the metered API |
| **Mistral / OpenRouter** | key in `scripts/.env` | best keyed-free (Mistral ~60 RPM; OpenRouter `openai/gpt-oss-20b:free`) |
| **Gemini 2.5 Flash** | key in `.env` | works, but 20 RPM → one-shot only |

The task, in every walkthrough: `Create reverse.py with reverse(s), plus test_reverse.py with a pytest test, then run pytest.`

## Walkthrough — opencode + a free provider
```
[rogueone] set -a; . ~/IdeaProjects/weyland/scripts/.env; set +a
[rogueone] cd ~/b15-scratch && opencode        # pick "Mistral Large" (or "gpt-oss 20b free", or Gemini)
```
It writes both files (relative paths, per the project `AGENTS.md`) and runs pytest → `6 passed`. Scriptable form:
```
[rogueone] opencode run "Create reverse.py with reverse(s) and test_reverse.py with a pytest test, then run pytest" -m mistral/mistral-large-latest --dir ~/b15-scratch --auto
```

## Walkthrough — Pi + a free provider
```
[rogueone] set -a; . ~/IdeaProjects/weyland/scripts/.env; set +a
[rogueone] cd ~/b15-scratch && pi --provider mistral --model mistral-large-latest
```
`~/.pi/agent/models.json` sets `compat.supportsDeveloperRole:false` + `supportsReasoningEffort:false` per provider —
without it Mistral/OpenRouter reject Pi's `developer` role / `reasoning_effort` with a **422**.

## Walkthrough — Cline / Codex on your ChatGPT sub (GPT-5.5)
```
[rogueone] cline auth        # → Sign in with ChatGPT → pick GPT-5.5;  then: cline -i -c ~/b15-scratch
[rogueone] codex login       # → Sign in with ChatGPT;                 then: cd ~/b15-scratch && codex "<task>"
```

## Verify
```
[rogueone] cat ~/b15-scratch/reverse.py; python3 -m pytest ~/b15-scratch -q
```
Expected: `def reverse(s): return s[::-1]` and `N passed`.

## What does NOT work (the durable findings)
- **Local models on rogueone's 16GB** — tool-call leaks (`qwen3-coder`), no tools (`deepseek-coder`), hallucinated tool
  names + context-collapse (`gpt-oss:20b`), un-disable-able thinking (`qwen3:30b-a3b`). Systemic 16GB wall.
- **The MLflow AI Gateway (B100 P4)** for agentic coding — hosted multi-turn tool loops crash MLflow
  (`json.loads("")`); response-stage guardrails block streaming. Fine for single-shot/serving, not agent loops.
- **Subscriptions as an API** — a **ChatGPT sub ≠ API access** (use "Sign in with ChatGPT"; the raw `sk-` key is dead,
  `insufficient_quota`); a **Claude Pro/Max** sub via a third-party agent is the B26 ToS gray area (sanctioned
  Claude-coding = Claude Code, B29).

# Coding Agents (B15) — local-model / free-hosted coding TUIs

Terminal AI coding agents (opencode / Cline / Pi) pointed at weyland's own model backends — "code with your own
models, on-LAN," the coding-side analogue of Open WebUI (B13). This runbook is the **verified working recipe** plus
the (extensive) findings from proving it out, so the setup never has to be re-derived from scratch.

## TL;DR — the working recipe

**opencode + Gemini 2.5 Flash (direct, free) = a working `$0` agentic coding TUI on rogueone.** Verified end-to-end:
it writes `reverse.py` + `test_reverse.py`, runs pytest, **6/6 pass**, `$0` (Gemini free tier).

- Install (rogueone): `npm install -g opencode-ai` → `~/.opencode/bin/opencode` (v1.18.x).
- Config: `~/.config/opencode/opencode.json` — a custom `@ai-sdk/openai-compatible` provider pointing **directly** at
  Google's OpenAI-compat endpoint (NOT the MLflow gateway — see below). Key read from `scripts/.env`, never chat/config.
- **The load-bearing gotcha:** the key must be in **opencode's process env**. `source` the `.env` in the *same shell*,
  then launch. opencode runs a **persistent server that captures env at startup** — a stale/pre-source server →
  Google 400 `Missing or invalid Authorization header`.

## Config — `~/.config/opencode/opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "gemini-direct": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Gemini (direct, free)",
      "options": {
        "baseURL": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "apiKey": "{env:GEMINI_API_KEY}"
      },
      "models": {
        "gemini-2.5-flash": { "name": "Gemini 2.5 Flash (direct, free)", "limit": { "context": 1048576, "output": 8192 } }
      }
    }
  }
}
```

- `{env:GEMINI_API_KEY}` resolves from opencode's process env at runtime — the key never lands in the config file.
- The `"limit"` block is **required** or the model is **hidden from the TUI model picker** (the `opencode models` CLI
  still lists it; the TUI filters custom models that lack context/output metadata).

## Launch (rogueone)

```
pkill -f opencode
set -a; . ~/IdeaProjects/weyland/scripts/.env; set +a
cd <project-dir> && opencode
```
Then pick **Gemini 2.5 Flash (direct, free)** in the model picker.

Non-interactive (proven form — good for scripts / CI / smoke tests):
```
opencode run "<task>" -m gemini-direct/gemini-2.5-flash --dir <project-dir> --auto
```

Optional `AGENTS.md` in the project dir pins path behavior (auto-loaded by opencode):
```
- Write files using paths RELATIVE to the current working directory (e.g. `reverse.py`). NEVER absolute paths.
- Do NOT create directories.
```

## Why direct-to-provider, NOT the MLflow AI Gateway (B100 P4)

The gateway is the governed front door for **single-shot** calls and **local Ollama serving** — but it is **NOT usable
for agentic coding**, for two independent reasons found the hard way:

1. **Hosted-provider multi-turn tool loop crashes it.** A single tool-call forwards fine, but the *follow-up* turn
   (assistant tool-call → tool result → continue) dies with a Python `json.loads("")` error surfaced as
   `stream error … "Expecting value: line 1 column 1 (char 0)"`. That error originates **inside MLflow** — not
   opencode, not the model. Single-shot chat and local Ollama tool-calls stream fine; hosted agentic multi-turn does not.
2. **Guardrails block streaming by design.** The Safety guard runs `AFTER` on `{{outputs}}`, forcing the gateway to
   buffer the whole completion — and every coding TUI requires SSE streaming. (This is why the eval temporarily
   unguarded endpoints; see the guard-exemption note in the gateway runbook. That scaffolding was **reverted** once
   agentic-via-gateway was ruled out.)

So: **coding agents point straight at the provider** (Gemini direct, or raw Ollama `.230:11434/v1` for local). The
gateway keeps its B100 P4 role (governed single-shot + serving) untouched.

## Local models — NOT viable on rogueone's 16GB (tested exhaustively)

Every local candidate failed as an agentic driver — and gpt-oss failed **identically direct and via the gateway**,
proving it's the models/Ollama, not the gateway:

| Model | Ollama tag | Failure |
|---|---|---|
| qwen3-coder | `qwen3-coder:30b` | tool-calls **leak as `<function=…>` text** (Ollama template not parsed to OpenAI `tool_calls`); plans (`todowrite` works) but can't execute writes |
| qwen3 instruct | `qwen3:30b-a3b` | **thinking mode can't be disabled via `/v1`** (`/no_think` ignored → 75s stalls) *and* tool-calls leak as JSON text |
| gpt-oss | `gpt-oss:20b` | **hallucinates tool names** (`container.exec`, `assistant`); total **context-collapse** into fabricated tasks |
| deepseek-coder | `deepseek-coder-v2:16b` | **no tool-calling support at all** — unusable in any agent harness |

**Root cause is systemic, not one bad model:** 16GB is too small (24–30B models spill ~40% to CPU *and* load at a
crippling `CONTEXT 4096` — Ollama's default, unsettable through `/v1`), compounded by per-model Ollama tool-template
parsing quirks and thinking-mode. `ollama ps` during a run shows `40%/60% CPU/GPU` + `CONTEXT 4096` — the wall in one line.

**If you want a local shot later:** `devstral-small-2:24b` (Mistral × OpenHands, **purpose-built** to drive agent
scaffolds, non-thinking, native function-calling) is the one model worth pulling — but it's a tight ~15GB-on-16GB fit
(desktop-freeze risk on rogueone). Also raise `OLLAMA_CONTEXT_LENGTH` on rogueone first (4096 is unusable for agentic
work). Until then, **hosted-direct (Gemini free) is the driver; local is a $0 offline convenience for light tasks only.**

## Harness verdict

- **opencode — PROVEN.** Clean tool protocol, caught *every* hallucinated tool, planned via `todowrite`, streamed,
  `$0`. Across every model tested the harness behaved correctly — **the model was always the variable.**
- **Cline, Pi — not yet tested.** Point them at `gemini-direct` the same way (Cline: `cline auth` → OpenAI-Compatible →
  base URL `https://generativelanguage.googleapis.com/v1beta/openai/`, model `gemini-2.5-flash`, key from `.env`; note
  Cline CLI bug #6924 may validate the key against openai.com — fallback is editing `~/.cline/data/globalState.json`).

## Gotchas (all learned this build)

- **Model hidden in TUI picker** → add a `"limit": { "context": …, "output": … }` block to the model entry.
- **400 Missing Authorization** → opencode's persistent server has a stale/empty env. `pkill -f opencode`, `source`
  the `.env`, relaunch in that shell. The CLI `opencode run` form is the reliable way to confirm auth in isolation.
- **`num_ctx` = 4096** on all local Ollama models via `/v1` → raise `OLLAMA_CONTEXT_LENGTH` on rogueone.
- The gateway streams **hosted** providers as a **single SSE frame** (whole answer at once), local Ollama as real
  incremental frames — both parse, but hosted single-frame + multi-turn tools is where the gateway bug bites.

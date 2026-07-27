# Coding Agents (B15) — local-model / free-hosted coding TUIs

Terminal AI coding agents (opencode / Cline / Pi / Codex) pointed at free hosted models or your ChatGPT subscription —
"code with capable models, on-LAN-ish, at `$0`," the coding-side analogue of Open WebUI (B13). This runbook is the
**verified working recipes** (all harnesses proven in-hand) plus the extensive findings, so setup never has to be
re-derived. Quick pick: **best = ChatGPT-sub GPT-5.5 via Cline/Codex; best keyed-free = Mistral / OpenRouter** (see the
provider matrix below). Local models on rogueone's 16GB are **not** viable (also below).

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

## Free / `$0` drivers — provider matrix

All OpenAI-compatible, all drop into the harnesses below. Confirmed 2026-07; rate limits from the free-tier research
(verify live — free tiers churn). Keys live in gitignored `scripts/.env`; `set -a; . scripts/.env; set +a` before launch.

| Driver | How | Rate limit | Notes |
|---|---|---|---|
| **ChatGPT sign-in → GPT-5.5** ⭐ | Cline / Codex → "Sign in with ChatGPT" | your ChatGPT plan's | **Best.** Frontier model, sub-*included* usage (NOT the metered API), far above any free tier. OpenAI *built* this for coding agents. |
| **Mistral** ✅ | `.env` key → `https://api.mistral.ai/v1` · `mistral-large-latest` | ~60 RPM, no card (SMS verify) | confirmed live/free; responses run slow. |
| **OpenRouter** ✅ | `.env` key → `https://openrouter.ai/api/v1` · `openai/gpt-oss-20b:free` | 20 RPM / 1000 RPD | confirmed live (cost 0); free slugs may train on inputs. |
| **Gemini 2.5 Flash** ✅ | `.env` key → Google OpenAI-compat · `gemini-2.5-flash` | **20 RPM** | works, but the limit 429s inside an agent loop — one-shot / light use only. |
| **opencode zen** | `opencode auth login` → opencode; `opencode/*-free` models | unpublished | opencode-only; "just work"; wants billing on file. |
| **Cline hosted (Grok Code Fast)** | Cline default provider | uncapped (promo) | Cline-only. |
| **Groq** ⏸ | `https://api.groq.com/openai/v1` · `openai/gpt-oss-120b` | 30 RPM / 1000 RPD, no card | **punted 2026-07 — signup was erroring** (`We had an issue`). The portable no-card winner *when it works*; doesn't train on your data. Retry later; key → `GROQ_API_KEY` in `.env`. |

**Skip** (limits too low for agent loops): Cerebras (5 RPM), GitHub Models (50–150/day), OpenAI **API** key (ours is `insufficient_quota` — dead). On Groq, `llama-3.3-70b` sunsets 2026-08-16 → use `openai/gpt-oss-120b`.

**Subscriptions:** ChatGPT **does** drive coding agents — via Cline/Codex "Sign in with ChatGPT" (the sub's *included* usage, not the metered API — note the raw `sk-` API key is separately dead, no credit). A **Claude Pro/Max** sub through a third-party agent stays the B26 ToS gray area (sanctioned Claude-coding = Claude Code, B29). opencode's OpenAI provider is **API-key only** → can't ride the ChatGPT sub; use Cline/Codex for the GPT-sub lane.

The multi-provider `~/.config/opencode/opencode.json` (gemini · mistral · openrouter · groq stub) and Pi's
`~/.pi/agent/models.json` are in place on rogueone — see the harness sections below for the exact shapes.

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

## Harnesses — all proven in-hand

Each verified end-to-end (writes both files, pytest green), all `$0`, same key-from-`.env` discipline. opencode / Cline /
Pi confirmed by the user across Gemini / Mistral / OpenRouter (+ Cline on the ChatGPT sub); Codex installed as the native
GPT-sub agent.

**opencode** (v1.18.x) — the config-file recipe above. `pkill -f opencode; source .env; opencode`.

**Cline** (v3.0.46) — two working drivers:

- **Recommended: "Sign in with ChatGPT" → GPT-5.5** (proven). `cline auth` → choose the OpenAI / ChatGPT sign-in option
  → authenticate in the browser → pick a model (GPT-5.5 confirmed). This uses your **ChatGPT subscription's included
  usage** (frontier model, **no metered API**, rate limits = your plan's, far above Gemini free's 20 RPM). Unlike the
  Claude Pro/Max case (B26 ToS gray area — Anthropic hasn't opened equivalent third-party sub auth), OpenAI *built* this
  sign-in for coding agents, so it's the intended path. Then `cline -i -c <project>` and pick the model.
- **Keyed fallback (Gemini free):** configure the OpenAI-compatible provider once with a *placeholder* key, feed the
  real key per-run from env so it never persists:
  ```
  cline auth -p openai-compatible -b "https://generativelanguage.googleapis.com/v1beta/openai/" -k "PLACEHOLDER-overridden-per-run" -m gemini-2.5-flash
  set -a; . ~/IdeaProjects/weyland/scripts/.env; set +a
  cline -P openai-compatible -k "$GEMINI_API_KEY" -m gemini-2.5-flash -i -c <project>
  ```
  The run command's `-k` overrides the persisted placeholder, so only the placeholder is ever on disk. (Gemini free =
  20 req/min → 429s under an agent loop; use the ChatGPT sign-in for real work.)

**Pi** (`@mariozechner/pi-coding-agent`, v0.73.x) — a **built-in `google` provider** (reads AGENTS.md by default), plus
custom OpenAI-compatible providers via `~/.pi/agent/models.json`:
```
npm install -g @mariozechner/pi-coding-agent
set -a; . ~/IdeaProjects/weyland/scripts/.env; set +a
cd <project> && pi --provider google  --model gemini-2.5-flash --api-key "$GEMINI_API_KEY"   # built-in google
cd <project> && pi --provider mistral --model mistral-large-latest                            # custom, from models.json
```
`~/.pi/agent/models.json` (env keys via `$VAR`) — **`compat` is load-bearing**: without `supportsDeveloperRole:false` +
`supportsReasoningEffort:false`, Mistral/OpenRouter reject Pi's `developer` role / `reasoning_effort` with a **422**:
```json
{ "providers": {
  "mistral":    { "baseUrl": "https://api.mistral.ai/v1",      "api": "openai-completions", "apiKey": "$MISTRAL_API_KEY",
                  "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false }, "models": [{ "id": "mistral-large-latest" }] },
  "openrouter": { "baseUrl": "https://openrouter.ai/api/v1",   "api": "openai-completions", "apiKey": "$OPENROUTER_API_KEY",
                  "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false }, "models": [{ "id": "openai/gpt-oss-20b:free" }] },
  "groq":       { "baseUrl": "https://api.groq.com/openai/v1", "api": "openai-completions", "apiKey": "$GROQ_API_KEY",
                  "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false }, "models": [{ "id": "openai/gpt-oss-120b" }] }
} }
```

**Codex** (`@openai/codex` v0.145) — OpenAI's own agent, the *native* home of ChatGPT sign-in and so the cleanest
GPT-5.5-via-sub path: `codex login` (→ Sign in with ChatGPT), then `cd <project> && codex "<task>"` (approve its
sandbox / file-write prompts). Installed; the GPT-sub lane is covered by **Codex (native) + Cline (proven)**.

**Verdict:** opencode, Cline, and Pi all **proven in-hand** (user-confirmed) across multiple `$0` drivers; Codex installed
as the native GPT-sub option. Clean tool protocols, real multi-step tool-use — the **model/provider** was always the
variable, never the harness. Best driver = **ChatGPT-sub GPT-5.5** (Cline/Codex); best keyed-free = **Mistral / OpenRouter**
(Gemini's 20 RPM 429s under an agent loop; Groq punted on a broken signup).

## Gotchas (all learned this build)

- **Model hidden in TUI picker** → add a `"limit": { "context": …, "output": … }` block to the model entry.
- **400 Missing Authorization** → opencode's persistent server has a stale/empty env. `pkill -f opencode`, `source`
  the `.env`, relaunch in that shell. The CLI `opencode run` form is the reliable way to confirm auth in isolation.
- **Pi 422 on Mistral/OpenRouter** → add `compat: {supportsDeveloperRole:false, supportsReasoningEffort:false}` to the
  provider in `~/.pi/agent/models.json` (they reject OpenAI's `developer` role / `reasoning_effort`).
- **Cline "provider not configured" / wrong key** → the run-command `-k` overrides the persisted auth; Cline's default
  `-P cline` provider (free Grok / your account) is separate from the keyed `openai-compatible` one.
- **`num_ctx` = 4096** on all local Ollama models via `/v1` → raise `OLLAMA_CONTEXT_LENGTH` on rogueone.
- The gateway streams **hosted** providers as a **single SSE frame** (whole answer at once), local Ollama as real
  incremental frames — both parse, but hosted single-frame + multi-turn tools is where the gateway bug bites.

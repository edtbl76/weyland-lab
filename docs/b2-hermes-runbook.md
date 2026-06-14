# B2 — Hermes Agent Runbook — weyland (CT 104)

Operational runbook for the Hermes agent platform: create/access the container, install + configure
Hermes, the model + Ollama tuning, and the gotchas hit during bring-up. Design rationale (lanes,
MCP, A2A) lives in [b2-agent-platform-design.md](b2-agent-platform-design.md); model serving is
[b7-ollama-runbook.md](b7-ollama-runbook.md).

---

**Live since 2026-06-13.** Unprivileged LXC `hermes` (CTID **104**) on the weyland Proxmox host.
- **Address:** `192.168.1.247` (DHCP-reserved on the router).
- **Spec:** 4 cores · 6 GB RAM · 20 GB rootfs on `local-zfs` · `nesting=1` (Debian 12).
- **What it is:** NousResearch/hermes-agent (MIT) — autonomous agent. Brain → Ollama `/v1`; system
  view (planned) → tool-server MCP. Sized lighter than the inference CTs (102/103) because it
  **offloads all inference to Ollama** — it's an orchestration workload, not a compute one.

## Access
No direct login — reach it through the weyland host: `ssh <host>` → `pct enter 104` → `root@hermes`.
One-offs: `pct exec 104 -- <cmd>`.

## Create the container (on weyland host)
```bash
pct create 104 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst --hostname hermes --unprivileged 1 --rootfs local-zfs:20
pct set 104 --net0 name=eth0,bridge=vmbr0,ip=dhcp
pct set 104 --cores 4 --memory 6144 --swap 0 --onboot 1 --features nesting=1
pct start 104
pct exec 104 -- ip -4 addr show eth0     # note the DHCP IP -> reserve it (192.168.1.247)
```

## Install Hermes (inside CT 104: `pct enter 104`)
```bash
apt update && apt install -y curl ca-certificates git
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes --version
```

> **PATH gotcha (minimal LXC):** the installer links `hermes` into `/usr/local/bin`, but a barebones
> Debian LXC's non-login shell (what `pct enter` gives) has a stripped `PATH` *without*
> `/usr/local/bin` → `hermes: command not found`. Fix once:
> ```bash
> echo 'export PATH=/usr/local/sbin:/usr/local/bin:$PATH' >> /root/.bashrc
> ```

## Configure (`hermes setup`)
Wizard picks (all to keep it **local-only** — no cloud keys, nothing off-LAN):
- **Provider:** `custom (direct API)` — *not* "Ollama Cloud" (that's hosted) or any branded provider.
- **Base URL:** `http://192.168.1.244:11434/v1` · **API key:** any non-empty string (`ollama`).
- **API compatibility:** `2. Chat Completions` (Ollama's OpenAI surface; also the path tool-calling
  rides — declare it, don't auto-detect).
- **Model:** `qwen3-coder:30b` (see below). **Terminal/sandbox backend:** `Local` (the CT *is* the
  sandbox; no nested Docker needed). **Platform:** Telegram only (new dedicated bot, separate from
  the B5 alerts bot). **Display name:** `weyland-ollama`.

Resulting `~/.hermes/config.yaml` provider block:
```yaml
custom_providers:
- name: weyland-ollama
  base_url: http://192.168.1.244:11434/v1
  api_key: ollama
  model: qwen3-coder:30b
  api_mode: chat_completions
  context_length: 65536      # MUST equal Ollama's OLLAMA_CONTEXT_LENGTH (see Context window)
```

## Model: `qwen3-coder:30b` (MoE) — measured, not assumed
Started with `mistral-small3.2:24b` (dense, non-thinking) — but dense 24B prefills at **~30 tok/s on
CPU** → multi-minute turns. Switched to **`qwen3-coder:30b` (30B-A3B MoE, ~3B active)** and measured:
- **~4.4× faster prefill** (154 vs 35 tok/s @ 1k tokens), validated end-to-end (fires tools, returns
  real `uname -a` output), and **no `<think>` blocks** (the Coder variant is direct).
- **Lesson: on CPU, *active* params (MoE), not total size, set speed.** The "bigger" 30B beat the 24B.
- Switch model live with `/model qwen3-coder:30b` (a config-file edit only sets the provider default,
  not the *active* selection — `/model` sets the active one).

## Ollama tuning (CT 102 — see [b7-ollama-runbook.md](b7-ollama-runbook.md))
Driven by this agent, applied on the Ollama CT. Two env vars in CT-102's drop-in:
`OLLAMA_CONTEXT_LENGTH=65536` and `OLLAMA_KEEP_ALIVE=-1`. The first gives room (Ollama's 4K default
truncated agent turns); the second keeps the model resident so turns stay warm on CPU.

## Context window — keep Hermes == Ollama
The model's native window is **262K**, but we serve **64K** (`OLLAMA_CONTEXT_LENGTH=65536`) — KV-cache
RAM caps it (262K ≈ ~58 GB KV → OOMs the 48 GB cgroup; 64K ≈ ~25 GB, fits). The 17K base prompt
(below) is a fixed tax, so 64K leaves ~47K for conversation.

**The status bar shows `…/262.1K` and stays there — that's COSMETIC, don't chase it.** The bar
displays the model's *native* capability (262K). The functional limit is set by `context_length: 65536`
on the provider block, which (per the config docs) *"controls when Hermes compresses history and
validates requests"* — i.e. Hermes compresses/validates at **64K**, matching what Ollama serves. So:
- **Do set** `context_length: 65536` on the `weyland-ollama` block (provider-level key, sibling to
  `base_url` — confirmed placement). It governs compression/validation even though the bar ignores it.
- The bar will still read 262K; that's the model headline, not the working window. Not a bug.
- **Backstop:** even if a session somehow exceeds 64K, Ollama (`num_ctx=65536`) does graceful
  *context-shift* (drops oldest tokens), not a crash. With the 17K base, you'd need ~47K of
  conversation to get near the cliff — rare. `/compress` or `/new` resets it.
- (`model_catalog.enabled: false` was tried as a suspected override; it made no difference — the bar's
  value comes from the model's own metadata via Ollama, not the catalog. Leave it as you like.)

## Tools & skills cost nothing — `tool_search` is on
**Counter-intuitive but measured:** enabling/disabling tools or skills does **not** change the prompt
size. With `tools.tool_search.enabled: auto`, Hermes keeps tools in a *searchable registry*, not the
system prompt — the model searches for tools on demand. We proved it bidirectionally: disabling
`skills` → 0 change, disabling `vision` → 0 change, *enabling* `spotify` → 0 change. **So the ~17K
context is purely Hermes's base framework prompt** (instructions, memory/goal/kanban scaffolding,
tool-search machinery), *not* tool schemas. **Implication: enable any *functional* tool freely — it's
free.** Only disable tools that can't function (no backend, e.g. GPU media-gen) so the model doesn't
try and fail. There is no "trim the toolset for speed" lever here.

## Prompt caching (why warm turns are fast)
llama.cpp caches the prompt-prefix KV on the Ollama side. The ~17K base prompt is prefilled **once**;
later turns reuse it (turn-2 prefill dropped from 13.5K tokens to ~111). Behavior:
- **Survives a Hermes restart** (cache lives on Ollama, keyed by prefix + resident model).
- **Dies on Ollama restart or model eviction** (any other model requested → `MAX_LOADED_MODELS=1`
  evicts qwen3-coder → next turn cold-prefills ~2–5 min).
- **Don't churn Ollama** if you want warm turns. Most "it's so slow" pain during bring-up was
  self-inflicted cache invalidation from restarting Ollama / swapping models.

## Manage it live — slash commands (no file editing, no nano)
Most config is adjustable in-session; prefer these over `hermes config edit` (which shells to nano):
- `/tools list | disable <names…> | enable <names…>` — toggle tools live.
- `/model [name] [--provider n] [--refresh]` — switch active model.
- `/usage` — token usage for the session. · `/statusbar` (`/sb`) — live context/model bar.
- `/config` — show config. · `/compress [here N]` — compact context. · `/new` — fresh session.
- To edit the file directly without nano: `EDITOR=vim hermes config edit`, or just `vim ~/.hermes/config.yaml`.

## Known noise (non-blocking)
- **`Auxiliary … 401 / Nous client unavailable`** — `auxiliary:` tasks (title-gen, etc.) default to
  Nous (needs `hermes auth`, which we don't use). Cosmetic; point them at `weyland-ollama` or ignore.
  (Vision auto-detected to the local provider correctly.)
- **`Lazy-installing edge-tts/elevenlabs/mistralai`** on every startup — TTS deps we don't use. Set
  `security.allow_lazy_installs: false` to stop it.
- Reset `logging.level: INFO` if you ever set it to DEBUG (it doesn't log request bodies anyway).

## Performance reference (CPU, qwen3-coder:30b @ 64K)
- **Prefill:** ~150 tok/s @ 1k ctx, degrading to ~60–90 tok/s as context fills (attention is O(n)).
- **Base prompt:** ~17K tokens (fixed; `tool_search` keeps tools out of it).
- **Warm turn (cached prefix):** ~6–17 s. **Cold turn (cache miss):** ~2–5 min (full base prefill).

## Front door (Telegram) — pending
A dedicated Telegram bot was created (separate from `@weyland_alerts_bot`). Wiring it as the live
front door needs the gateway: `hermes gateway install` (run the binary by absolute path in the unit —
same PATH caveat as above). Deferred until the MCP system-view server is in.

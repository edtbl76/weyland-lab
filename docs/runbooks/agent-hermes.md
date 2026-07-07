# B2 — Hermes Agent Runbook — weyland (CT 104)

Operational runbook for the Hermes agent platform: create/access the container, install + configure
Hermes, the model + Ollama tuning, and the gotchas hit during bring-up. Design rationale (lanes,
MCP, A2A) lives in [../concepts/agent-platform-design.md](../concepts/agent-platform-design.md); model serving is
[model-serving-ollama.md](model-serving-ollama.md).

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

## Ollama tuning (CT 102 — see [model-serving-ollama.md](model-serving-ollama.md))
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

## Diagnostics — measure context, prefill, and warmth

The exact commands used during bring-up to answer "why is it slow / is it hung / how big is the
prompt." All on the **weyland host** unless noted.

```bash
# Loaded model? served CONTEXT? pinned? (UNTIL=Forever means KEEP_ALIVE=-1 held)
pct exec 102 -- ollama ps

# Prefill rate + EXACT prompt token count of recent turns — the "why slow" ground truth.
pct exec 102 -- journalctl -u ollama --no-pager -n 80 | grep -iE 'prompt processing|prompt eval|tokens per second'
#  "prompt eval ... N tokens (... tokens per second)"  -> total prompt size + prefill speed
#  "prompt processing ... progress=0.NN"               -> live prefill progress mid-turn

# Grinding or hung? llama-server near 100% = working (slow prefill); ~0% while waiting = stalled.
pct exec 102 -- top -bn1 | head -12
pct exec 102 -- bash -lc 'ps -eo pcpu,comm --sort=-pcpu | head -4'

# Verify Ollama env vars actually applied (HOST, MAX_LOADED_MODELS, CONTEXT_LENGTH, KEEP_ALIVE)
pct exec 102 -- systemctl show ollama -p Environment

# Network reachability hermes CT (104) -> ollama CT (102)
pct exec 104 -- curl -s http://192.168.1.244:11434/v1/models
```

In-session (inside `hermes`): **`/usage`** (token usage after a turn), **`/statusbar`** (live
context/model bar — but its window number is the model's cosmetic native max; see Context window).

> **Reading the prefill log:** a single turn logs `prompt processing` lines climbing to a final
> `prompt eval ... N tokens`. `N` = the full prompt size; the trailing `tokens per second` is the CPU
> prefill rate (degrades as context grows — attention is O(n)). This is how we measured the dense-24B
> (~35 tok/s) vs MoE-30B (~154 tok/s) gap and confirmed `tool_search` (toggling tools → N unchanged).

## Performance reference (CPU, qwen3-coder:30b @ 64K)
- **Prefill:** ~150 tok/s @ 1k ctx, degrading to ~60–90 tok/s as context fills (attention is O(n)).
- **Base prompt:** ~17K tokens (fixed; `tool_search` keeps tools out of it).
- **Warm turn (cached prefix):** ~6–17 s. **Cold turn (cache miss):** ~2–5 min (full base prefill).

## MCP system-view server (B2 v1 — live 2026-06-14)

The agent's "view into the system": read-only MCP tools over HTTP, built **into** the tool-server
(it already holds the RAG/status/health logic). One server; both agents connect by URL (N+M).

**Exposes (read-only v1):** `status`, `context_search`, `context_ask`, `list_models` — the tool-server
routes carrying a `tags=["mcp"]` decorator. The write/act routes (`/pipeline/trigger`, `/evals/run`,
`/evals/score`) are deliberately untagged → excluded. Read+act is a later slice, gated on B14.

**Tool-server changes** (`services/weyland-tool-server/`):
- `main.py`: `from fastapi_mcp import FastApiMCP`; `tags=["mcp"]` on the 4 read routes; at end of file
  (after all routes are registered): `FastApiMCP(app, name="weyland-system-view", include_tags=["mcp"]).mount_http()`.
- `Dockerfile`: added `fastapi-mcp` to the pip install.
- Mounts at `/mcp` on the existing app + port (8080 → NodePort 30080) — no new service/port.

**Build → load into k3s → deploy** (image is `weyland-tool-server:local`, `imagePullPolicy: Never` —
local k3s image, no registry; built with **docker** on mother — *this process was previously undocumented*):
```bash
# [on rogueone] ship changed files to mother
rsync -a services/weyland-tool-server/main.py services/weyland-tool-server/Dockerfile emangini@mother:~/lab/weyland-platform/services/weyland-tool-server/
# [on mother] VERIFY the shipped file BEFORE building (catches stale source — see lessons)
grep -n 'mcp.mount' ~/lab/weyland-platform/services/weyland-tool-server/main.py    # expect mount_http()
# [on mother] build, import into k3s containerd, roll out
cd ~/lab/weyland-platform/services/weyland-tool-server
docker build -t weyland-tool-server:local .
docker save weyland-tool-server:local | sudo k3s ctr images import -
kubectl rollout restart deployment/weyland-tool-server -n weyland && kubectl rollout status deployment/weyland-tool-server -n weyland
# [on mother] confirm the DEPLOYED code (not just the shipped file)
kubectl exec -n weyland deploy/weyland-tool-server -- grep -n 'mcp.mount' /app/main.py
```
Docker caches up to `COPY main.py`, so rebuilds are fast — the slow HF-model bake layer is reused.

**Register in Hermes** (CT 104) — add a top-level section to `~/.hermes/config.yaml` (column 0):
```yaml
mcp_servers:
  weyland:
    url: "http://192.168.1.243:30080/mcp"
```
Then `/reload-mcp` → `➕ Added: weyland · 🔧 4 tool(s) from 1 server(s)`. `/tools list` shows
`weyland  all tools available` (grouped under the server, not enumerated; `tool_search` keeps them
searchable, not pinned — the "0 active" count is normal). OpenClaw later adds the *identical* line.

**Validated 2026-06-14:** "What's the Weyland system status?" → agent searched the `status` tool,
called it, returned LIVE backend health (pgvector/qdrant/weaviate/neo4j OK + the 6 live Ollama models).

### Read+act: the `/mcp-act` action surface (B14 read+act — live 2026-06-16)

The three **action** tools (`pipeline/trigger`, `evals/run`, `evals/score`) live on a **separate MCP mount**
at `/mcp-act` (not `/mcp`). Every call is audited by the guardrail `act` hook (`policy.audit`, shadow) →
`guardrail_verdicts` (with `actor` from the trusted `X-Forwarded-Consumer` header). Audit-only today — nothing
blocks; the enforcing policy gate (allowlist/rate-limit) is deferred to the B35 pairing.

**Lane decision (who gets to act):** **Hermes registers `/mcp-act`; Claude Code does NOT — it stays read-only
on `/mcp`.** Hermes is the *resident operator* (reactive over Telegram when you're away from the keyboard, so it
needs act tools); Claude Code is the *builder* with you already at the terminal (it hands you `curl`/`kubectl`
and you run them — no autonomous act tools needed). One actor on the system is the cleaner thing to govern.

**Register the act surface in Hermes** (CT 104) — add a second entry under `mcp_servers` in
`~/.hermes/config.yaml`:
```yaml
mcp_servers:
  weyland:
    url: "http://192.168.1.243:30080/mcp"        # read-only (existing)
  weyland-act:
    url: "http://192.168.1.243:30080/mcp-act"     # action tools (B14 read+act)
```
Then `/reload-mcp` → expect `➕ Added: weyland-act · 🔧 3 tool(s)`. `/tools list` shows both servers.

**Cost caveat:** `evals/run` (~40-60 min CPU) and `evals/score` (~70 min CPU) compete with the single loaded
Ollama model — the tool descriptions say so (from the route docstrings) so Hermes weights them appropriately.
`pipeline/trigger` is cheap (hash-gated re-ingestion). Glance at the act audit after the first few days:
```bash
kubectl exec -i -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT created_at, actor, left(reason,50) AS reason FROM guardrail_verdicts WHERE hook='act' ORDER BY id DESC LIMIT 20;"
```
Rollback is one line: remove the `weyland-act` block and `/reload-mcp`.

### Hard-won lessons (don't repeat these)
- **Transport: `mount_http()` (Streamable HTTP), NOT `mount()`/`mount_sse()`.** Hermes's `url:` client
  POSTs `initialize`; an SSE endpoint is GET-only → **`405 Method Not Allowed` → 0 tools**. A raw
  `curl /mcp` that streams `event: endpoint` + `: ping` does **not** prove it works (GET is valid for
  SSE) — only the agent handshake does.
- **Stale-source trap: `grep` the shipped file on mother BEFORE `docker build`.** Our first build
  deployed old `mount()` code because the rsync pre-dated the edit; the image "worked" on curl but
  Hermes 405'd. The build is only as correct as the file that actually arrived.

## OpenClaw — the delegate (Docker on vm-100) + MCP registration

**OpenClaw runs in Docker on the openclaw VM (vm-100) — there is NO bare `openclaw` host command.**
Run its CLI via `docker exec`; its config lives at `/home/node/.openclaw/openclaw.json` *inside the
container* (it runs as user `node`) — manage it through the CLI, don't hand-edit.
```
# [on openclaw VM] find the gateway container, then run the CLI inside it
docker ps --format '{{.Names}}'                         # → openclaw-openclaw-gateway-1
docker exec -it openclaw-openclaw-gateway-1 openclaw <cmd>
```

**`openclaw mcp` subcommands** (OpenClaw 2026.5.31 — native MCP, stdio + HTTP/SSE):

| cmd | purpose |
|---|---|
| `add` | add one server from flags — **probes before saving** (the safe path; bad config fails closed without writing) |
| `list` / `show` | list configured servers / show one or the full MCP config |
| `probe` | connect and list available capabilities |
| `status` | transport status without connecting |
| `reload` | dispose cached MCP runtimes → new config used on the next turn |
| `configure` / `set` / `unset` | update operator controls / set from a JSON object / remove a server |
| `tools` | per-server include/exclude tool filters |
| `login` / `logout` | OAuth-authenticated servers |
| `serve` | expose OpenClaw's *channels* over MCP stdio (the reverse direction) |
| `doctor` | static setup checks |

**Register the Weyland system-view** (same URL Hermes uses — the N+M payoff; check `mcp add --help`
for exact flags first since the config is fragile):
```
# --transport streamable-http MUST match the tool-server's mount_http() endpoint (an sse/streamable
# mismatch is the 405 that bit Hermes). `add` probes before saving, so success == connected + validated.
docker exec openclaw-openclaw-gateway-1 openclaw mcp add weyland --url http://192.168.1.243:30080/mcp --transport streamable-http
docker exec openclaw-openclaw-gateway-1 openclaw mcp list       # confirm it saved
docker exec openclaw-openclaw-gateway-1 openclaw mcp reload     # apply on next turn
```
**Use `mcp add` (probes-before-saving), NOT a hand-edit of `openclaw.json`** — every prior manual edit
broke the gateway (fails closed). The CLI writes valid JSON and validates the server before committing.

## Front door (Telegram) — live 2026-06-14

A dedicated Telegram bot (separate from `@weyland_alerts_bot`) is the live front door. Inbound DM →
allowlist check → agent turn → reply. The gateway is a **headless systemd service**, distinct from the
interactive `hermes` REPL: same agent, no keyboard.

**Install the gateway** (inside CT 104): `hermes gateway install` creates
`/etc/systemd/system/hermes-gateway.service`. Its `ExecStart` is
`/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main gateway run` and it pins
`VIRTUAL_ENV=/usr/local/lib/hermes-agent/venv` — **remember that venv path; it's where deps must land.**

**Token + allowlist live in `~/.hermes/.env`, NOT `config.yaml`.** Setup ships a ~23 KB `.env` template
(every var present, commented). Set just these two (uncommented):
```
TELEGRAM_BOT_TOKEN=<botfather token>
TELEGRAM_ALLOWED_USERS=<your numeric telegram user id>   # locks the bot; clears the "no allowlist" warning
# GATEWAY_ALLOW_ALL_USERS=true   # opposite stance — open access; do NOT use on a token-bearing bot
```
> Watch for paste cruft: a stray BotFather line (`Use this token to access the HTTP API:`) had landed
> in `OPENROUTER_API_KEY=` — harmless (OpenRouter unused) but delete it so it doesn't mislead.

### The dependency trap (the bring-up blocker)
The gateway died on a restart loop (`status=1/FAILURE` every few seconds) logging:
```
WARNING gateway.run: Telegram: python-telegram-bot not installed
WARNING gateway.run: No adapter available for telegram
```
**The headless gateway does NOT lazy-install messaging backends** — only the interactive REPL/tool path
does (pyproject confirms telegram/slack/etc. are *meant* to lazy-install, but a cold systemd boot hits
the import and fails closed). Install the **pinned** version (the adapter is written against `22.6`;
latest would API-mismatch) **into the gateway's venv** — the installer is `uv`, parked at
`/root/.hermes/bin/uv` (not on PATH; the venv has no `pip`/`ensurepip`):
```
# use `uv pip install` (additive, like pip) — NOT `uv sync` (prunes the venv to the lock, would rip out
# REPL-lazy-installed extras like edge-tts). Target the exact venv the unit runs.
VIRTUAL_ENV=/usr/local/lib/hermes-agent/venv /root/.hermes/bin/uv pip install \
  --python /usr/local/lib/hermes-agent/venv/bin/python "python-telegram-bot[webhooks]==22.6"
/usr/local/lib/hermes-agent/venv/bin/python -c "import telegram, telegram.ext; print(telegram.__version__)"  # expect 22.6
systemctl restart hermes-gateway
```
After restart: `systemctl is-active hermes-gateway` → `active`, `systemctl show hermes-gateway -p NRestarts`
→ **`NRestarts=0`** (the real success signal — the unit treats "no adapter" as fatal, so a stable
non-flapping process means the adapter loaded). We run **polling**, not webhooks (a LAN bot has no public
HTTPS callback URL); `[webhooks]` rides along only because that's how Hermes pins it, unused.

> **`journalctl` looks frozen after a healthy restart — not a bug.** The startup banner goes through
> `print()` → stdout, which Python **block-buffers** under systemd (stdout is a pipe, not a TTY), so it
> never flushes on a long-lived process. The earlier WARNINGs appeared because they go through the
> *logging* module (unbuffered). A quiet journal + `active`/`NRestarts=0` = running fine. A healthy poll
> loop is silent anyway (it logs warnings/errors, not routine `getUpdates`).

### First turn is the documented cold prefill (~3.5 min)
First DM after a (re)start cold-prefills the ~18K prompt (17K base + MCP reg + your msg). Watch it on the
Ollama CT — `pct exec 102 -- journalctl -u ollama --no-pager -n 30 | grep -iE 'prompt eval|progress'`
shows `progress=` climbing with the rate decaying (141→69 tok/s, O(n) attention). `llama-server` at
~800% CPU = grinding, not hung. Reply lands ~1 min after prefill hits 1.0; **subsequent turns reuse the
cached prefix → warm ~6–17 s** (see Prompt caching). Meanwhile Hermes DMs a live status:
`⏳ Working — iteration 1/150, waiting for stream response (… no chunks yet)` — "no chunks" = still
prefilling (no first token yet); "iteration N/150" = the agent's reason→act loop budget, not an error.

### Home channel + the "not supported on the web version" messages
On first contact Hermes asks: `📬 No home channel is set for Telegram … Type /sethome`. The **home
channel** is where it delivers cron-job results and cross-platform messages (no inbound to reply to).
**Run `/sethome` in the target chat** or cron output is orphaned. Hermes's home-channel prompt and the
⏳ status pings render as *"This message is not supported on the web version of Telegram"* in
**web.telegram.org** (effect/format the web client can't draw) — they're fine; **read them in the mobile
or desktop app.**

**Validated 2026-06-14:** DM from the allowlisted user → "typing" → agent cold-prefilled (~3.5 min) →
real reply in Telegram. Gateway `active`, `NRestarts=0`.

## Kanban — self-management + roadmap co-pilot (B27, live 2026-06-17)

Hermes's **native, durable SQLite Kanban** (`hermes kanban`) — boards-per-workstream, task deps, atomic
claims, profile **workers in isolated workspaces**, `decompose`/`specify`/`swarm`. The dispatcher runs inside
the existing `hermes-gateway` (no extra daemon, no container, no Postgres). Design:
[../../aidlc-docs/construction/b27-kanban-design.md](../../aidlc-docs/construction/b27-kanban-design.md).

**Planning brain split:** planning (`decompose`/`specify`) runs on **Gemini free via the gateway**; the
default brain + the workers that *execute* tasks stay local `qwen3-coder`. Wired by:
- A `custom` provider **`weyland-model-gateway`** → `http://192.168.1.243:30400/v1`, key = the LiteLLM
  master key, api_mode chat_completions, model `gemini-flash`. Add via `hermes model`.
  **⚠ the `hermes model` wizard sets this as the DEFAULT** — revert the default back to local:
  ```
  hermes config set model.default qwen3-coder:30b
  hermes config set model.base_url http://192.168.1.244:11434/v1
  hermes config set model.api_key ollama
  ```
- Pin **only** the two planning aux lanes to the gateway in `~/.hermes/config.yaml` (leave the others local):
  ```
  auxiliary.kanban_decomposer:  { provider: custom, model: gemini-flash, base_url: http://192.168.1.243:30400/v1, api_key: <master-key> }
  auxiliary.triage_specifier:   { provider: custom, model: gemini-flash, base_url: http://192.168.1.243:30400/v1, api_key: <master-key> }
  ```
- `hermes kanban init` (creates `kanban.db`), then `systemctl restart hermes-gateway`.

**(b) Roadmap co-pilot — the `weyland-roadmap` board.** One-way mirror of `docs/backlog.md`:
`nodes/weyland/hermes/roadmap-sync.py` (on CT 104 at `/root/roadmap-sync.py`) `curl`s the raw backlog from the
public repo, parses each `### B/U —` item + status (top "## DONE" bullets / priority markers), and upserts
cards (`--idempotency-key <id>` dedups; DONE → `complete`). Cron: `17 */6 * * *`. **The human owns
`backlog.md`; Hermes annotates the board, never edits the backlog.**

**Safety model (important):** roadmap cards are created **unassigned**. The dispatcher only spawns workers for
**assigned** tasks (`decompose` assigns; the sync deliberately does not) — so the roadmap board is a **passive
read mirror**, proven by `running 0` while the `default` worker was busy on assigned tasks. *Note:*
`--initial-status blocked` does **not** stick (Hermes auto-unblocks a card with no real blocker → it drifts to
`ready`); the unassigned-never-claimed property is what keeps it safe, not the status.

**⚠ `decompose` autonomously EXECUTES.** A decomposed task fans into children **assigned to a profile**, and
the dispatcher runs them — planning on Gemini, **shell execution in CT 104 workspaces**. A wiring test
("backup Postgres to MinIO") really started building it. Only decompose/assign work you actually want done.

**View / operate:**
```
hermes kanban --board <slug> ls            # snapshot  (boards: default, weyland-roadmap)
hermes kanban --board <slug> stats         # per-status counts
hermes kanban --board <slug> watch         # live event stream
hermes kanban assignees                    # worker profiles + running/todo counts
```
**Kill runaway tasks:** `reclaim` the running ones (releases the worker claim), then `archive`:
```
hermes kanban --board default reclaim <id>
hermes kanban --board default archive <id…>
hermes kanban --board default gc           # clean archived workspaces/logs (optional)
```

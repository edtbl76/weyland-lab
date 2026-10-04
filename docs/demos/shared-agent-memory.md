# Demo — Shared agent memory (B182)

One store of agent memory for every coding agent: the Markdown notes in `~/agent-memory/weyland` on rogueone, read
natively by Claude Code (its memory dir is a symlink to them) and served over MCP by Basic Memory, which Bifrost exposes
to Codex and the others. Sequence: [diagrams/flow-shared-memory.md](../diagrams/flow-shared-memory.md). Runbook:
[runbooks/shared-agent-memory.md](../runbooks/shared-agent-memory.md).

**Cleanup:** every step that writes deletes its probe note in the same step; nothing is left behind (verified: 0 probe
files after each run).

## CLI walkthrough — RUN 2026-10-03

**1. The store answers, holds every note, and both write paths work.**

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && ~/.local/bin/uv run -q --with mcp python scripts/check-shared-memory.py
```
```
1. reachable OK — 21 tools at http://127.0.0.1:8765/mcp
2. indexed OK — the index holds all 214 notes on disk
3. mcp write OK — landed as _check/check-shared-memory 3412a606a2.md
4. native OK — a plain-file note was searchable after 0s
OK — the shared memory store is reachable, complete, writable over MCP and sees native writes.
```

**2. Negative case — the store is down → exit 2, "unreachable", never "no memory".** Run before the service existed:
```
UNREACHABLE — the shared memory store did not answer (http://127.0.0.1:8765/mcp: …). Memory is NOT empty; it is down.
exit=2
```

**3. Claude Code ↔ Codex — B182's first acceptance criterion.** Over Codex's exact route (`https://bifrost.weyland.lab/mcp`
with the `x-bf-vk` header from `~/.codex/config.toml`):
```
tools via Bifrost (coding-agents VK): 199 total, 21 Agent_Memory
A. Claude Code native write -> found via Codex's route: True after 0s
B. write via Codex's route -> file in Claude Code's memory dir: True after 0s
```

**3b. OpenCode — a real agent session (criterion 6).** A note written natively, then OpenCode on Gemini asked to find it
using only the memory tool (run from `/tmp`, so it cannot read the repo's notes instead):

[rogueone]
```
cd /tmp && set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && opencode run -m gemini-direct/gemini-2.5-flash "Use ONLY the Agent_Memory search_notes tool (from the bifrost MCP server) — do not read any files. Find the memory note whose text contains the word quokka<tag> and reply with exactly that note's name field, nothing else."
```
```
⚙ bifrost_Agent_Memory-search_notes {"output_format":"json","query":"quokka9302a9d9"}
_opencode-probe-9302a9d9
```
RUN 2026-10-03, 28 s, exit 0. (It answers with the note's title — the file name — because permalinks are off.)

**3c. Codex — a real agent session.** Same shape as 3b, on Codex's ChatGPT-plan model:

[rogueone]
```
cd /tmp && codex exec --skip-git-repo-check --ephemeral --sandbox read-only "Use ONLY the Agent_Memory search_notes tool from the bifrost MCP server — do not run shell commands or read files. Find the memory note whose text contains the word wombat<tag> and reply with exactly that note's title, nothing else."
```
```
approval: never
mcp: bifrost/Agent_Memory-search_notes started
mcp: bifrost/Agent_Memory-search_notes (completed)
_codex-probe-1184b8de
```
RUN 2026-10-03, 28 s, exit 0, ~10k tokens (ChatGPT plan, not a paid API).

**4. The firewall — only mother reaches :8765.**

[mother]
```
kubectl -n weyland exec deploy/weyland-guard -c weyland-guard -- python -c "import urllib.request; urllib.request.urlopen('http://192.168.1.230:8765/mcp',timeout=5)"
```
→ an `HTTP Error 400` traceback: it **reached** the MCP server (which expects a POST).

[rogueone]
```
docker run --rm alpine:3.20 sh -c 'apk add -q curl >/dev/null; curl -s -o /dev/null -m 6 -w "%{http_code}\n" http://192.168.1.230:8765/mcp'
```
→ `000`: **blocked** (a non-mother source). Control: the same container reaches Ollama on `:11434` → `200`.

**5. The watchdog — secrets + health every 15 min.**

[rogueone]
```
systemctl --user start agent-memory-watch.service && journalctl --user -u agent-memory-watch --since -1min --no-pager -o cat | grep agent-memory-watch:
```
```
agent-memory-watch: exit 0 — no secrets; store healthy
```
Negative case (scratch dir, not the real notes): gitleaks 8.21.2 on a note holding a `ghp_…` token → `exit=1 leaks found: 1`;
a clean note → `exit=0 no leaks found`. The watchdog's verdicts for both, plus "scanner failed" and "store unreachable",
are pinned by `scripts/tests/agent-memory-watch.bats` (7 cases).

**6. The notes are never rewritten by the server.** Checksums of all 214 files before the move, after the move, and
after the service started: identical.

## UI walkthrough (UAT — eyes on)

1. **Bifrost** — `https://bifrost.weyland.lab` → **MCP clients**. Confirm `Agent_Memory` is listed, **connected**, URL
   `http://192.168.1.230:8765/mcp`, with ~21 tools.
2. **Bifrost → Virtual keys → `coding-agents`** — `Agent_Memory` attached with all tools; **`operator`** — attached with
   only the read tools (`search_notes`, `read_note`, `view_note`, `read_content`, `build_context`, `recent_activity`,
   `list_directory`, `search`, `fetch`).
3. **Uptime Kuma** — once `KUMA_MEMORY_PUSH_URL` is set (runbook § Watchdog): the **agent-memory** push monitor is
   green and updates every ~15 min.

## Expected result

- One copy of the notes; Claude Code's memory path is a symlink to it; the server changes none of them.
- Any coding agent finds a note another one wrote, in under a second, through Bifrost.
- Only mother can reach the server; everything else on rogueone is unchanged.
- A secret written into memory is flagged within 15 min; a store that stops answering is reported as unreachable.

# Shared agent memory — Basic Memory on rogueone (B182)

One store of agent memory that every harness reads and writes. The store **is a directory of Markdown notes** on
rogueone — `/home/edwardmangini/agent-memory/weyland/` (`MEMORY.md` index + one note per fact). Claude Code writes it
natively (its auto-memory path is a symlink to it); **Basic Memory** serves the same files over MCP so every other
agent can search, read and write them — directly on rogueone, or through Bifrost from mother. One copy, no sync.
Design + evidence: [design/shared-agent-memory-design.md](../design/shared-agent-memory-design.md). Rules for agents:
`AGENTS.md` § Agent memory.

| Piece | Where |
|---|---|
| Notes (the store) | rogueone `~/agent-memory/weyland/` — backed up nightly by restic (`backup-paths.conf`) |
| Claude Code's path | `~/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/memory` → **symlink** to the notes |
| Server | Basic Memory 0.23.2, user unit `basic-memory.service`, MCP streamable HTTP on `:8765` |
| Gateway | Bifrost MCP client `Agent_Memory` → `http://192.168.1.230:8765/mcp`; coding-agents key = all tools, operator key = read-only |
| Firewall | rogueone ufw: `:8765` admits only mother (`192.168.1.243`); everything else unchanged (default allow) |
| Watchdog | user timer `agent-memory-watch` every 15 min — gitleaks + read-only health → Kuma push monitor |

All commands below run on **rogueone** unless the label says otherwise.

## Check it works (the acceptance test + demo)

```
cd /home/edwardmangini/IdeaProjects/weyland && ~/.local/bin/uv run -q --with mcp python scripts/check-shared-memory.py
```
Four checks: reachable · every note on disk is in the index · a note written over MCP lands as a file · a note written
as a plain file is searchable within 60 s. Exit 0 pass · 1 a check failed (named) · 2 **unreachable** — the store is
down, NOT empty. `--read-only` runs the first two only (what the watchdog uses).

## Install / reinstall

Basic Memory 0.23.2 depends on `fastmcp==4.0.0b1` (a pre-release). Install from the **frozen** list, never with a bare
`--prerelease=allow` (that alone pulled betas of pydantic, sentry-sdk, logfire):
```
~/.local/bin/uv tool install basic-memory==0.23.2 --python 3.12 --constraints /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/basic-memory/requirements.txt --prerelease=allow
```
```
cp /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/basic-memory.service ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now basic-memory.service
```
**The two settings that protect the notes** (in the unit): `BASIC_MEMORY_DISABLE_PERMALINKS=true` and
`BASIC_MEMORY_ENSURE_FRONTMATTER_ON_SYNC=false`. With Basic Memory's defaults the first index **rewrote 207 of 213
notes** (added `permalink:`, re-wrapped descriptions, changed timestamp format, prepended frontmatter to `MEMORY.md`).
Never start it against the notes without them. To bump the version: re-freeze the list in `python:3.12-slim`
(`pip install basic-memory==<v> && pip freeze`), re-install, run the check, and diff the notes' checksums before/after.

## Firewall (Basic Memory has no auth)

Enabled 2026-10-03 so that **nothing changes except `:8765`** (default incoming stays allow; forwarding stays ACCEPT so
Docker networking is untouched):
```
sudo ufw default allow incoming
sudo sed -i 's/^DEFAULT_FORWARD_POLICY=.*/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw
sudo ufw allow from 192.168.1.243 to any port 8765 proto tcp
sudo ufw deny 8765/tcp
sudo ufw enable
```
Prove both sides (mother pod reaches it; a non-mother source does not):

[mother]
```
kubectl -n weyland exec deploy/weyland-guard -c weyland-guard -- python -c "import urllib.request,urllib.error; urllib.request.urlopen('http://192.168.1.230:8765/mcp',timeout=5)" ; echo "exit $? (an HTTP 400 traceback = reached the server)"
```
[rogueone]
```
docker run --rm alpine:3.20 sh -c 'apk add -q curl >/dev/null; curl -s -o /dev/null -m 6 -w "%{http_code}\n" http://192.168.1.230:8765/mcp'
```
→ `000` (blocked). Docker traffic arrives over `docker0`, not loopback, so ufw filters it — a valid "other host".

## Bifrost registration (how mother's agents reach it)

Source of truth: `Agent_Memory` in `scripts/register_bifrost_mcp_clients.py` and in `SCOPING` of
`scripts/attach_bifrost_vk_mcp.py` (coding-agents = all tools; operator = `MEMORY_READ`). Order matters
([mcp-gateway.md](mcp-gateway.md) § Restore):

[mother]
```
kubectl -n weyland exec -i deploy/weyland-guard -- python - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_bifrost_mcp_clients.py
```
[mother]
```
kubectl -n weyland exec -i deploy/bifrost -c bifrost -- /runtime/usr/bin/python3 - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/attach_bifrost_vk_mcp.py
```
[mother]
```
kubectl -n weyland rollout restart deploy/bifrost
```
Bifrost logs `Connected to MCP server 'Agent_Memory'` when it can reach the store. Tools then appear as
`Agent_Memory-search_notes`, `Agent_Memory-write_note`, … (21 on the coding-agents key).

## Per-harness config (B182 criterion 6)

| Harness | How it reaches the store | Config | Read test |
|---|---|---|---|
| Claude Code | native files — its memory path is a symlink to the store | `~/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/memory` → `~/agent-memory/weyland` | `check-shared-memory.py` step 4 (plain-file note searchable < 1 s) |
| Codex | Bifrost `/mcp`, coding-agents key | `~/.codex/config.toml` `[mcp_servers."bifrost"]` + `http_headers.x-bf-vk` | 2026-10-03: a real `codex exec --sandbox read-only` session called `bifrost/Agent_Memory-search_notes` and returned the Claude-written note (28 s); also its exact route both directions, < 1 s |
| OpenCode | Bifrost `/mcp`, its key | `~/.config/opencode/opencode.json` `mcp.bifrost` (`type: remote`, `headers.x-bf-vk`) | 2026-10-03: `opencode run -m gemini-direct/gemini-2.5-flash` called `bifrost_Agent_Memory-search_notes` and returned the Claude-written note (28 s) |
| Pi / Cline | the files directly (same host) | `AGENTS.md` § Agent memory | — |

**OpenCode needs its provider keys in the environment:** its providers read `{env:GEMINI_API_KEY}` etc., so run it
with `scripts/.env` loaded (`set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a`) or the model
call fails with `Missing or invalid Authorization header` — the memory side is unaffected.

## Watchdog

`scripts/agent-memory-watch.sh`, every 15 min (user timer `agent-memory-watch.timer`): gitleaks 8.21.2 over
`~/agent-memory` (findings **redacted**) + `check-shared-memory.py --read-only`. Exit 0 clean · 1 a finding (secret,
incomplete index) · 2 could not check (scanner failed, store unreachable). Logs:
```
journalctl --user -u agent-memory-watch --since -1h --no-pager -o cat | grep agent-memory-watch:
```
**Kuma (set up 2026-10-03):** a **Push** monitor "agent-memory" (heartbeat interval **1200 s**, Telegram notification);
its push URL — **without** the `?status=…` query, which the watchdog appends — is `KUMA_MEMORY_PUSH_URL` in
`scripts/.env`. If that variable is missing the watchdog logs `KUMA_MEMORY_PUSH_URL unset — verdict NOT reported to Kuma`.

**A secret was found:** list where, with values redacted, then remove the line from the note:
```
docker run --rm --user "$(id -u):$(id -g)" -v "$HOME/agent-memory:/scan:ro" zricethezav/gitleaks:v8.21.2 dir /scan --no-banner --redact --report-format json --report-path /dev/stdout | python3 -c "import json,sys;[print(f['RuleID'],f['File'],'line',f['StartLine']) for f in json.load(sys.stdin)]"
```
Rotate the credential too — it has been on disk and in the restic backup.

## Restore (DR)

The notes are plain Markdown; the Basic Memory index (`~/.basic-memory/`) is rebuilt from them on start, so only the
notes matter. Restore from the nightly restic snapshot into scratch and diff against the live copy — the drill in
[nodes/rogueone/backup/README.md](../../nodes/rogueone/backup/README.md) § Restore test:
```
cd /home/edwardmangini/IdeaProjects/weyland && set -a && . nodes/rogueone/backup/.env && set +a && restic restore latest --target /tmp/restore-test --include "$HOME/agent-memory" && diff -r "$HOME/agent-memory" /tmp/restore-test/"$HOME"/agent-memory && echo "RESTORE OK"
```
To recover lost notes, copy them from `/tmp/restore-test/$HOME/agent-memory/weyland/` back into
`~/agent-memory/weyland/`, then run the check (the server re-indexes them within seconds).

## Roll back (undo B182)

Stop the service, then put the notes back where Claude Code expects them:
```
systemctl --user disable --now basic-memory.service agent-memory-watch.timer
```
```
rm /home/edwardmangini/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/memory && mv /home/edwardmangini/agent-memory/weyland /home/edwardmangini/.claude/projects/-home-edwardmangini-IdeaProjects-weyland/memory
```
Then remove `Agent_Memory` from the two Bifrost scripts and re-run the three registration steps.

## Gotchas

- **`list_directory` is paginated** (10 per page); the header carries the total (`214 total items`) — use it, not the
  first page, to count the index.
- **`write_note` returns before the file exists** (`checksum: unknown`) — poll for the file.
- **`write_note` takes `directory`**, not `folder`.
- **The MCP Python client renamed things** in recent versions: `streamable_http_client` (was `streamablehttp_client`),
  two yielded streams (was three), `is_error` / `input_schema` (were camelCase).
- **Search quality is moderate**: 3 of 5 known answers in the top 5 with semantic search (2 of 5 keyword-only). The
  `MEMORY.md` index stays the primary recall path; search is the second.

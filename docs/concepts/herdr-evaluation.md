# Herdr evaluation (B257)

**Status: verdict ADOPT alongside Emdash for interactive multi-agent work, [ADR-0018](../adr/0018-adopt-herdr-for-interactive-multi-agent-work.md)
(Linear EMA-358).** Runbook: [runbooks/herdr.md](../runbooks/herdr.md).

## Why

The lab runs several coding agents on rogueone (Claude Code in long-running sessions, plus Codex, OpenCode, Cline and Pi;
`AGENTS.md` is harness-neutral) and Emdash's unattended conveyor (B179, ADR-0006). There is no single place to see which
agent is working, blocked on a question, or idle, and an interactive session dies with its terminal unless it runs as a
background job. Herdr is a terminal runtime that claims to cover both. Owner, 2026-11-20: "Add a HIGH to eval/impl
Herdr."

## Facts (primary sources, read 2026-11-22)

Sources: the repository `github.com/herdrdev/herdr` (moved from `ogulcancelik/herdr`; the old URL redirects), its
v0.9.5 source tree (commit `2ecf19a9`, 2026-10-14), the docs bundled in that tree (`docs/next/website/`), and the
GitHub release API.

| Fact | Value | Source |
|---|---|---|
| Current stable release | **v0.9.5**, published 2026-10-14 (previews ship between stables, e.g. `preview-2026-10-14-fbd2ae23927f`) | GitHub releases |
| License | Apache-2.0 | `LICENSE` |
| Form | one Rust binary (no Electron), a background server plus a TUI client; tmux-style prefix keys and mouse | README, `Cargo.toml` |
| Linux build | `herdr-linux-x86_64`, 30,285,672 bytes, `sha256:14d9e8bc8b4a9e0118d77c32266f76d461f09b40342eb23752960bd89f59929d` (aarch64 also published) | release assets (GitHub-computed digests) |
| Persistence | terminals keep running in the server when the client closes or SSH drops; after a server or machine restart the layout is restored and supported agents can be resumed, but **the original processes do not survive** | README; `session-state` doc |
| Agent state | `idle` / `working` / `blocked` per pane, rolled up to tab and workspace | `agents.mdx` |
| How state is detected | Herdr finds the agent process in the pane and matches the live bottom of the screen against per-agent **detection manifests**; agents with an integration that reports state (OpenCode, Pi, Kimi, Kilo) use their reports instead. `blocked` only when a known approval, question or permission screen matches; an unknown prompt falls back to `idle` (`default_known_agent_idle_fallback`), which the docs warn about | `agents.mdx` |
| Supported agents | Claude Code, Codex, Copilot CLI, Cursor, OpenCode, Pi, Droid, Devin, Kimi, Kilo, Hermes, Qwen Code, Grok, Antigravity and more (with integrations); Amp, Kiro, Gemini CLI and **Cline** state-only, the last two "less tested" | `agents.mdx` |
| Integrations | `herdr integration install claude` writes `~/.claude/hooks/herdr-agent-state.sh` and adds `SessionStart` hook entries to `~/.claude/settings.json` (session identity only; Claude's state still comes from the screen). Codex likewise reports identity only | `integrations.mdx` |
| Socket API | local socket (no network listener found): create/list/close workspaces, tabs and panes; read, split and send input to panes; list, read, prompt, wait on and start agents; subscribe to events; `herdr api schema --json` prints the protocol | `socket-api.mdx` |
| Agent-to-agent | an agent in a pane can spawn panes, prompt another agent and wait until it is genuinely blocked (`agent prompt --wait`, `agent wait`); the docs warn that `idle` is not authorization to type into an approval dialog | README; `agents.mdx` |
| Other features | saved SSH machines in one window (installs or downloads Herdr on the remote host), plugins (a marketplace), git worktree helpers | README; `src/remote/attach.rs` |

### Network behaviour (every call in the v0.9.5 source)

There is no HTTP client library in its dependencies; every HTTP call shells out to `curl` (a plain GET with no request
body: `src/noninteractive_process.rs`). Found by searching every `curl_command()` call site and every URL in `src/`:

| Call | When | Default | How to turn it off |
|---|---|---|---|
| `https://herdr.dev/latest.json` (or `preview.json` on the preview channel) | background version check at start-up and every 30 minutes (`AUTO_UPDATE_CHECK_INTERVAL`, `src/app/mod.rs`; observed in § Network check) | **on** | `[update] version_check = false` |
| `https://herdr.dev/agent-detection/index.toml`, then each listed manifest | background check at start-up and every 30 minutes (the catalog plus 22 per-agent rule files); **valid rule updates are applied automatically** without a restart (`src/detect/manifest_update.rs`) | **on** | `[update] manifest_check = false` (or point `HERDR_AGENT_DETECTION_MANIFEST_CATALOG_URL` elsewhere) |
| Homebrew formula JSON | only for a Homebrew install | n/a here | |
| the release asset URL from the manifest | only on `herdr update` (manual); the download is checked against the manifest's SHA-256 | manual | don't run it |
| Herdr binary download to a remote host | only when attaching a saved SSH machine | manual | don't use remote machines |
| `install.sh` / `install.ps1` | the documented installer (`curl … | sh`) | not used | install the release binary directly |

No telemetry, analytics or crash reporting was found (searched for `telemetry`, `analytics`, `posthog`, `sentry`
and similar). The two background checks do reveal to herdr.dev that a client is running (IP address, every 30
minutes, curl's default user agent). The manifest check also lets herdr.dev change detection rules on this machine
without a release, so both are turned off for the lab install. Scrollback and session state stay in Herdr's local
state directory; no call ships terminal content.

## Install (2026-11-22)

Owner: "yes, install it". `herdr-linux-x86_64` v0.9.5 downloaded from the GitHub release, `sha256sum -c` against the
release digest (`OK`), installed with `install -m 0755` to `/home/edwardmangini/.local/bin/herdr`; `herdr --version`
prints `herdr 0.9.5`. `~/.config/herdr/config.toml` was written **before** the first run with `[update]
version_check = false` and `manifest_check = false`. No installer script, no integrations, no hooks.

## Trial (rogueone, 2026-11-22)

A named session (`herdr --session b257 server`, headless, under `strace -f -e connect,execve`), one workspace in the
repo, Claude Code (Opus 5.5, the owner's subscription) and Codex 0.157 (GPT-6-Astra, the owner's ChatGPT subscription)
in side-by-side panes, driven through Herdr's CLI. Both agents were given real, read-only lab tasks that feed this
evaluation: Claude summarised Emdash's conveyor (ADR-0006, `software-factory.md`), Codex summarised the harnesses in
`multi-harness.md`. Both answered correctly.

| Criterion | Result | Evidence |
|---|---|---|
| (a) state detection, Claude Code | **yes** | parallel run: `working` from 23:09:26 to `idle` at 23:09:46, sampled every 2 s; a Bash write outside the repo raised Claude's permission dialog and Herdr showed `blocked` within 4 s (rule `bash_permission_prompt`); after declining, back to `idle` |
| (a) state detection, Codex | **partly** | its command-approval dialog showed `blocked` within 4 s (rule `osc_title_blocked`), and `working`/`idle` tracked the run. **But** Codex's start-up question ("Background server has incompatible feature settings", three options) showed as **`idle`** (rule `osc_title_idle`): exactly the failure the issue names. The docs say unknown prompts fall back to `idle` |
| (b) sessions survive a client close and an SSH drop | **yes** | a real TUI client held on a pseudo-terminal (120x40), confirmed attached, then killed with SIGHUP (what an SSH drop sends) and with SIGKILL: Claude (pid 1731695) and Codex (pid 1732222) stayed alive with the same pids, and the server kept answering. Tested locally; rogueone has no key-based SSH to itself, and none was added. A server or machine restart is documented not to keep the processes |
| (c) one agent hands work to another | **yes, mechanically** | from a shell pane inside Herdr (`HERDR_ENV=1`): `herdr agent prompt codex1 '…count docs/adr/0*.md…' --wait` returned exit 0 when Codex finished, and its answer (17) matched the real count. An agent doing this itself needs permission to run `herdr`; approving another agent's permission prompt on the owner's behalf was refused by the session's safety check, so that step is the owner's call |
| (d) no phoning home, or it can be turned off | see § Network check | |
| (e) overlap | see § Compared with what the lab already runs | |
| (f) resource cost | **negligible** | server RSS 20-22 MB per session; ~1 s CPU over 8 minutes with two agents (under strace); binary 30 MB; state 84 KB |

Side finding: during the trial Codex updated itself (it ran `curl` against `releases.openai.com` for 0.171.0). That is
Codex's own behaviour, not Herdr's, but it is a second tool on rogueone that updates itself unpinned.

## Network check (criterion d)

Two isolated Herdr sessions with no agent in them (so every connection is Herdr's own), run side by side for 36 minutes
(23:16-23:52) under `strace -f -e connect,execve`: `netoff` with the lab config, `neton` with Herdr's default config
(`HERDR_CONFIG_PATH` pointing at an empty file) as the control that proves the method sees the calls.

| Session | Successful `curl` runs | Internet connections | Requests |
|---|---|---|---|
| `netoff` (lab config, both checks off) | **0** | **0** | none |
| `neton` (defaults) | 48 | 240 (Cloudflare addresses behind herdr.dev) | 2 rounds, at start-up and 30 minutes later, each `latest.json` + `agent-detection/index.toml` + 22 per-agent rule files |

So with defaults, Herdr sends 24 HTTPS GETs to herdr.dev at start-up and every 30 minutes; the server log confirms the
two checks (`update.check.start` at 04:16:02Z and 04:46:02Z). A first count of 2,544 `curl` execs was wrong: most were
failed `execve` attempts while the shell walked a ~106-entry `PATH`; only the 48 that returned 0 are runs. **Verdict on
(d): yes, it phones home by default, and it can be turned off; with the lab config it made no connection at all.**

## Compared with what the lab already runs (criterion e)

| | Emdash conveyor (ADR-0006, B179) | Claude Code background sessions (how the owner works) | Herdr |
|---|---|---|---|
| What it is | unattended, scheduled runs (`agent-ready-nightly`, 04:00), one worktree per run, Claude Code with auto-approve | one long interactive Claude Code session plus background jobs, kept by Claude Code itself | a terminal runtime: panes for any harness, kept by a background server |
| Survives a closed terminal or dropped SSH | yes (Emdash runs them) | yes, for Claude Code | yes, for every harness (tested) |
| Shows working / blocked / idle | no: "done" only means dispatched; a hung run is found by reading its transcript (Claude's trial answer named this gap) | for Claude Code sessions only | for 20+ harnesses in one sidebar; blocked approvals caught for Claude Code and Codex, but an unfamiliar Codex prompt showed `idle` |
| One agent drives another | no | Claude Code sub-agents, Claude only | yes, across harnesses (`agent prompt --wait`), given permission to run `herdr` |
| Sees the conveyor's runs | yes | no | no: Emdash owns those terminals, so Herdr does not close the hung-run gap |

**What Herdr adds:** one view and one persistence layer across *different* harnesses (Codex, OpenCode, Pi, Cline next to
Claude Code), with blocked-state alerts and cross-harness hand-off. **What it duplicates:** persistence and status for
Claude Code, which the owner's single long session and its background jobs already have. **What it does not touch:**
Emdash's unattended runs.

## Verdict (2026-11-23)

**Adopt alongside Emdash for interactive multi-agent work.** The reasoning, as put to the owner: on the merits nothing
disqualified it (persistence real, hand-off works, cost negligible, network fully controllable), and for a single long
Claude Code session it duplicates what Claude Code already does; its value is several *different* harnesses side by
side. The owner, 2026-11-23: "At some point, I will likely have multiple agents. This is a viable capability."

Adopted with: the pinned v0.9.5 binary, the detection-rule updates off and the version check on (owner, 2026-11-23:
"yes, turn the version check on"; verified: one GET of `latest.json` at start-up) (config in `nodes/rogueone/herdr/`,
placement `host_config`); the runbook; a LikeC4 element; `multi-harness.md`; and, as Closing Gaps, the machine inventory's new
`binary` kind (the collector could not see any of the 28 standalone binaries in `~/.local/bin`, Herdr included) with
Port's `installed_package` blueprint extended to accept it. Not adopted: the Claude Code integration hook, `herdr
update`, plugins and remote machines (each an owner decision if wanted later).

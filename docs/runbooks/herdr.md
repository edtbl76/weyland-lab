# Herdr — running several coding agents side by side (B257)

Herdr is a terminal runtime for coding agents: a background server keeps each agent's terminal alive when the client
closes or SSH drops, marks every pane `working`, `blocked` or `idle`, and lets one agent prompt and wait on another over
a local socket. Adopted 2026-11-23 for interactive work with several agents at once, alongside Emdash's unattended
conveyor ([ADR-0018](../adr/0018-adopt-herdr-for-interactive-multi-agent-work.md)). The evaluation, the trial and the
network check are in [concepts/herdr-evaluation.md](../concepts/herdr-evaluation.md). Everything here is on **rogueone**.

| | |
|---|---|
| Version | **v0.9.5** (2026-10-14), pinned; Apache-2.0; `github.com/herdrdev/herdr` |
| Binary | `/home/edwardmangini/.local/bin/herdr` (cataloged as kind `binary` by the machine inventory, identity = its SHA-256) |
| Config | `/home/edwardmangini/.config/herdr/config.toml`, repo copy `nodes/rogueone/herdr/config.toml` (placement `host_config`: the nightly host check fails if they differ) |
| State | `~/.config/herdr/sessions/<name>/` (sockets, logs, layout snapshots), `~/.local/state/herdr/` |
| Network | one GET of `herdr.dev/latest.json` at start-up and every 30 minutes (the version check, owner 2026-11-23); detection-rule updates off (see § Network) |

## Use it

Start or reattach the default session in your terminal (detach with `ctrl+b q`; the agents keep running):

[rogueone]
```
herdr
```

Inside it, split panes and start an agent in each (`claude`, `codex`, `opencode`, `pi`, `cline`). The sidebar rolls
each agent's state up to its tab and workspace: a `blocked` agent needs an answer, `idle` is ready for the next prompt.
From any shell, the CLI shows the same thing:

[rogueone]
```
herdr agent list
```

Hand work from one agent to another, or script it (from a pane inside Herdr; `--wait` returns when the agent finishes):

[rogueone]
```
herdr agent prompt <agent-name> "<the task>" --wait --timeout 600000
```

An agent can run these itself only if its permissions allow the `herdr` command; approving that is the owner's call
per agent. A named session isolates experiments from the default one: `herdr --session <name>`.

## Caveats from the trial

- **`idle` is not proof the agent is free.** Herdr marks `blocked` only for approval and question screens it knows.
  In the trial, Codex's start-up question ("Background server has incompatible feature settings", three options)
  showed as `idle`. Read the pane before typing into an agent Herdr calls `idle` after something unusual:
  `herdr agent read <name>`, or `herdr agent explain <name>` for the rule that decided.
- **A machine or server restart ends the agents.** The layout comes back and supported agents can be resumed, but the
  processes do not survive. Closing the client or losing SSH does not end them (tested with SIGHUP and SIGKILL).
- **Detection rules are frozen at the binary's version**, because their remote updates are off. New agent screens are
  recognised after a Herdr upgrade, or with a local rule in `~/.config/herdr/agent-detection/<agent>.toml`.
- **Do not run `herdr update`, the `install.sh` installer, or `herdr integration install`** without an owner decision:
  the first two bypass the pinned install; the third adds a `SessionStart` hook to `~/.claude/settings.json`.

## Network

Herdr has no HTTP library; it calls `curl`. With its defaults it sends 24 HTTPS GETs to herdr.dev at start-up and every
30 minutes: `latest.json` (version check) and the agent-detection catalog plus 22 rule files, which it applies
automatically. The lab config keeps the version check, which only shows "update available" (this is how a new
release gets noticed), and turns the rule updates off, because they change how agent state is read without a release:

```toml
[update]
version_check = true
manifest_check = false
```

Measured: with both off, an isolated session made **0** internet connections in 36 minutes (2026-11-22), against 48
requests with the defaults; with this config, start-up made exactly one request, to `latest.json` (2026-11-23). To
re-check after an upgrade, run a session under `strace` and list the `curl` runs (count only `execve` calls that
return 0: the shell tries every `PATH` entry before finding `curl`):

[rogueone]
```
strace -f -qq -e trace=connect,execve -o /tmp/herdr-net.log herdr --session netcheck server
```

Then, after 35 minutes, `herdr --session netcheck server stop` and
`grep 'execve("[^"]*curl' /tmp/herdr-net.log | grep '= 0$' | grep -oE 'https://[^"]+' | sort | uniq -c` must list only
`https://herdr.dev/latest.json`.

If `~/.local/state/herdr/agent-detection/remote/` ever holds files, rules were fetched from herdr.dev (a run with the
checks on); delete that directory so the pinned binary's own rules apply.

## Upgrade (pinned, by hand)

1. Read the release notes at `github.com/herdrdev/herdr/releases` and the `[update]` section of the new
   `configuration` docs (a renamed key would turn a check back on).
2. Download the Linux asset and verify it against the digest GitHub shows for the release:

[rogueone]
```
curl -fsSL -o /tmp/herdr-linux-x86_64 https://github.com/herdrdev/herdr/releases/download/<tag>/herdr-linux-x86_64 && echo "<sha256>  /tmp/herdr-linux-x86_64" | sha256sum -c -
```

3. Stop the running server (agents in it end), install, and check the version:

[rogueone]
```
herdr server stop; install -m 0755 /tmp/herdr-linux-x86_64 /home/edwardmangini/.local/bin/herdr && herdr --version
```

4. Re-run the network check above, update the version in this runbook, the evaluation doc and the LikeC4 element. The
   next nightly inventory run records the new `sha256:` value.

## Uninstall

[rogueone]
```
herdr server stop; rm /home/edwardmangini/.local/bin/herdr
```

Then delete `~/.config/herdr` and `~/.local/state/herdr`, remove the two placement rows (`tool:rogueone/herdr` and
the config file), the LikeC4 element, and `nodes/rogueone/herdr/`.

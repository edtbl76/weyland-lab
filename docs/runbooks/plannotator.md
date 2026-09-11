# Runbook — Plannotator (plan + diff review for coding agents) (B167)

Local, OSS ([plannotator.ai](https://plannotator.ai/), `backnotprop/plannotator`, MIT/Apache-2.0) review
surface for the lab's coding agents: review an agent's **plan** before it runs and annotate its **git diff**,
pushing feedback back to the agent in one click. Eval + rationale:
[../concepts/plannotator-eval.md](../concepts/plannotator-eval.md). **Workstation tool** (runs beside the agent
on rogueone, like [Emdash](parallel-agent-supervisor.md)) — **not** a cluster service; nothing in Argo or the
app registry.

## Install (pinned + verified + hardened)

The installer is user-space (`~/.local/bin`, no sudo) and verifies a **SHA-256 checksum + a GitHub build
attestation** before `chmod +x`. Pin the version rather than blind-installing latest — get the tag from
https://github.com/backnotprop/plannotator/releases (v0.27.14 as of 2026-09-11):

```bash
curl -fsSL https://plannotator.ai/install.sh | bash -s -- --version v0.27.14 --no-extras --model-invocable none
```

`--no-extras --model-invocable none` skips the AI-invocable wiring, the `~/.codex` auto-touch, and the
semantic-diff sidecar — add those deliberately, not by surprise. Then keep it **fully LAN-local** (Ask-AI and
link-sharing are the only features that egress) by adding to `~/.bashrc`:

```bash
export PLANNOTATOR_AI=disabled PLANNOTATOR_SHARE=disabled
```

Ensure `~/.local/bin` is on `PATH`.

## Wire Claude Code (primary)

**These are Claude Code prompt commands — type them at the Claude Code prompt, NOT the shell** (pasting them
into bash gives `No such file or directory`):

```text
/plugin marketplace add backnotprop/plannotator
/plugin install plannotator@plannotator
```

Restart Claude Code. That installs the plugin (its skills + the `PermissionRequest`/`ExitPlanMode` hook).
Manual alternative (no plugin system): a `PermissionRequest` hook matching `ExitPlanMode` in
`~/.claude/settings.json` running the `plannotator` command. Secondary agents: **Codex** auto-wires a `Stop`
hook (macOS/Linux/WSL); **OpenCode** adds `"plugin": ["@plannotator/opencode@latest"]` to `opencode.json`.

Optional: the VS Code extension `backnotprop.plannotator-webview` for in-editor review tabs.

## The two flows

- **Plan review** — when an agent finishes planning and calls **`ExitPlanMode`**, the hook fires, a **local
  server** opens a **browser** review UI on the plan markdown. Annotate + **Approve** (agent proceeds) or
  **Deny** (your annotations return to the agent as structured feedback; on revision the diff shows what
  changed). This is the flagship path — it hooks Claude Code's native plan gate directly.
- **Diff review** — type `/plannotator-review` (uncommitted changes / a GitHub PR URL / GitLab MR /
  GitButler). A browser diff viewer opens: annotate lines, stage/unstage, **send** feedback to the session, or
  **Approve** ("LGTM"). Also `/plannotator-annotate <file|folder|url>` and `/plannotator-last`.

The UI is a **local port** (random local; `:9999` in remote/SSH mode) — **no `*.weyland.lab` DNS entry
needed**. On a headless/SSH box set `PLANNOTATOR_REMOTE=1`.

## Gotchas (learned wiring it up 2026-09-11)

- **Slash commands are not shell.** `/plugin …` and `/plannotator-*` are typed at the Claude Code prompt;
  pasted into a terminal they error with `No such file or directory`. Keep them out of any shell fence you copy.
- **`/plannotator-review` is user-invocation-only** — the plugin sets `disable-model-invocation`, so Claude
  cannot launch the diff review for you (and must not work around it). You run it; the agent acts on the
  feedback it returns. The `ExitPlanMode` plan-review path, by contrast, is agent-initiated (the agent presenting
  a plan trips the hook).
- **A closed review returns "Review session closed without feedback"** (exit 0) — that means nothing to
  address, not an error.
- Config/state: `~/.plannotator/config.json`; disable egress features with the env vars above.

## Upgrades

`/plugin marketplace update` (drops stale `plannotator:*` command entries), then re-run the pinned installer
with a newer `--version`.

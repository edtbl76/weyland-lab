# Plannotator — evaluation (B167)

> B167's eval half (2026-09-11). Goal: give the lab a **human review/steer surface** over its coding
> agents — review an agent's **plan** before it executes and annotate its **git diff** — with feedback
> pushed back to the agent in one click. **$0 / OSS / self-hostable / LAN-only** lens. Ties to [[b104]]
> (dev-tooling survey + **Emdash** parallel supervisor), [[b166]] (**Serena** agent context), and **B15**
> (the lab's local-model coding agents). Tool: [Plannotator](https://plannotator.ai/) — `backnotprop/plannotator`.

## What it is

A **local** review tool for AI coding agents. Two flows:

1. **Plan review** — when the agent finishes planning (Claude Code: calls **`ExitPlanMode`**), Plannotator
   intercepts the approval, a **local server opens a browser review UI**, you annotate the plan markdown
   (comments/redlines), then **Approve** (agent proceeds) or **Deny** (your structured annotations go back to
   the agent as feedback; on revision the diff shows what changed). It hooks the *exact* plan-approval seam.
2. **Code review** — `/plannotator-review` opens a diff viewer (uncommitted changes / GitHub PR / GitLab MR /
   GitButler) with a file tree + side-by-side diff; annotate lines, stage/unstage, send feedback to the agent
   session; Approve sends "LGTM".

Plus `/plannotator-annotate <file|folder|url>` (markdown/HTML) and `/plannotator-last` (annotate the agent's
last message). The UI is a **browser** page served by a local process (random local port; `:9999` in remote/SSH
mode) — **not** a desktop GTK app, so the B104 **Bruno-snap tofu** class of rendering bug does not apply here.

## Per-harness fit (the lab's real drivers — B15: Claude Code primary; Codex/OpenCode secondary)

| Harness | Wiring | Fit |
|---|---|---|
| **Claude Code** (primary) | **Plugin** — `/plugin marketplace add backnotprop/plannotator` → `/plugin install plannotator@plannotator` → restart. **Or** a manual **`PermissionRequest` hook** matching `ExitPlanMode` in `~/.claude/settings.json` running the `plannotator` command. | ✅ **First-class** — hooks `ExitPlanMode` (Claude Code's native plan gate) directly. |
| **Codex** | Experimental **`Stop` hook + skills**, auto-wired on macOS/Linux/WSL by the installer (touches `~/.codex`). | ✅ supported (auto). |
| **OpenCode** | JSON config — add `"plugin": ["@plannotator/opencode@latest"]` to `opencode.json`. | ✅ supported. |
| (also Copilot CLI, Gemini CLI, Kiro, Droid, Pi, Amp) | plugin / hook / npm ext per agent | — not the lab's drivers |

All three of the lab's coding agents are supported, Claude Code most deeply.

## $0 / OSS / LAN-only fit

- **License:** MIT **or** Apache-2.0. **OSS ✅.**
- **Local by default:** "no usage telemetry or analytics; plans, diffs, annotations, drafts, history, config
  stay local." **But** four features egress if used: URL-fetch (Jina Reader), GitHub/GitLab PR retrieval,
  **Ask-AI / Review-Agents** (→ the configured LLM provider), and **link-sharing** (upload). **Lab hardening:
  set `PLANNOTATOR_AI=disabled` + `PLANNOTATOR_SHARE=disabled`** (or point Ask-AI at the lab Bifrost/LiteLLM
  gateway) so it stays fully LAN-local. This is the key fit finding — clears the $0/LAN bar *once hardened*.
- **Install (supply-chain — inspected 2026-09-11):** `curl -fsSL https://plannotator.ai/install.sh | bash`
  installs a precompiled binary (bundled Bun runtime) to `~/.local/bin/plannotator` — **user-space, no sudo,
  no `eval` of remote content**. The script **verifies a SHA-256 checksum AND a GitHub build attestation**
  (`gh attestation` / the attestations API) before `chmod +x`. Trustworthy. The lab-safe form is a **pinned
  version** and the lean flags: `bash -s -- --version vX.Y.Z --no-extras --model-invocable none` (skips the
  AI-invocable wiring + the Codex `~/.codex` auto-touch + the semantic-diff sidecar — install those deliberately,
  not by surprise). Don't blind-`curl|bash` latest — pin + verify (the script supports it).
- **Not a lab k8s deploy:** like **Emdash** (B104), Plannotator is a **workstation tool** — it runs beside the
  agent on rogueone, not as an Argo service. Zero cluster footprint.

## Recommendation

**Strong fit — adopt on the workstation, hardened.** It fills the exact gap B104/B166 left open: B104 gave
parallel agents (Emdash), B166 gave them structural context (Serena), and Plannotator is the **human review
layer** — the plan-approval gate stops being a wall of terminal text, and diffs get line-level annotation with a
one-click round-trip. Claude Code (the lab's primary) is its deepest integration (`ExitPlanMode` hook). Install
pinned + attestation-verified, with `PLANNOTATOR_AI`/`PLANNOTATOR_SHARE` disabled for a fully LAN-local tool.

**The install + wiring + UAT are operator steps** (workstation binary + Claude Code plugin/hook + browser
eyes-on) — batched below. Keep/skip is decided after the eyes-on round-trip.

## Operator steps (batched — workstation, browser, eyes-on)

1. **Install the binary (pinned + verified), hardened:**
   ```bash
   curl -fsSL https://plannotator.ai/install.sh | bash -s -- --version <latest-release-tag> --no-extras --model-invocable none
   # ensure ~/.local/bin is on PATH; then keep it LAN-local:
   #   export PLANNOTATOR_AI=disabled PLANNOTATOR_SHARE=disabled   (in your shell profile)
   ```
   (Pick `<latest-release-tag>` from https://github.com/backnotprop/plannotator/releases.)
2. **Wire Claude Code** — in an interactive session: `/plugin marketplace add backnotprop/plannotator` →
   `/plugin install plannotator@plannotator` → restart. (Or the manual `PermissionRequest`/`ExitPlanMode` hook.)
3. **(optional) VS Code extension** `backnotprop.plannotator-webview` for in-editor review tabs.
4. **Eyes-on UAT (the round-trip):** in Claude Code, plan a real weyland change so the agent hits `ExitPlanMode`
   → the browser review UI opens → annotate + **Deny** → confirm the agent revises against your notes. Then
   `/plannotator-review` on an uncommitted diff → annotate a line → send → confirm it lands in the session.
5. **Keep/skip call** + (if keep) a runbook beside `parallel-agent-supervisor.md` + a demos-ledger row.

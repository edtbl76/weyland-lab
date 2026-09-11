# Runbook — parallel-agent supervisor (B104)

A supervisor over the coding-agent CLIs the lab already has (Claude Code · opencode · codex): **one git
worktree per task**, several agents running at once, and one board to compare diffs / open PRs / merge.
The survey ([concepts/ai-dev-tooling-survey.md](../concepts/ai-dev-tooling-survey.md)) rated this
**optional / low for a solo lab** — it is convenience (one board, parallel diffs, ticket intake), not a
new capability, since the worktree-per-task pattern is already achievable directly with the CLIs. This
runbook is the operator recipe if/when that convenience is wanted; nothing is deployed into the cluster.

## Recommended: Emdash (active, MIT)

[`generalaction/emdash`](https://github.com/generalaction/emdash) — the **open-source agentic development
environment** (YC W26, MIT). A **desktop app** that runs 30+ CLI agents in parallel, each task in its own
git worktree, and reviews/merges from one dashboard. It fits this lab's topology unusually well:

- drives the CLIs already installed here (Claude Code, codex, opencode);
- **git-worktree-per-task** — "Add Task" creates a worktree; each worktree runs its own agent;
- **issue intake from Linear** (the lab's declared status source of truth, [[linear-status-source-of-truth]])
  **and GitHub** — send a ticket straight into an agent;
- **remote development over SSH** — point it at `rogueone` / `mother`, matching the lab's split.

Repo: https://github.com/generalaction/emdash · Docs: https://emdash.com/docs/ .

Install (operator workstation — it is a local desktop app, LAN-safe, no cluster footprint):

```
# Linux
# .deb (recommended — installs system-wide, no FUSE/sandbox). Verified on rogueone 2026-09-10 (v1.2.4):
curl -L -o /tmp/emdash.deb https://github.com/generalaction/emdash/releases/download/v1.2.4/emdash-amd64.deb
sudo apt install /tmp/emdash.deb && emdash
# — or the AppImage (no root; needs libfuse2, or run --appimage-extract-and-run):
#   curl -L -o ~/emdash.AppImage https://releases.emdash.sh/emdash-x86_64.AppImage && chmod +x ~/emdash.AppImage && ~/emdash.AppImage

# macOS
brew install --cask emdash
```

Then in the app: add a project (a local git repo, or an SSH remote), pick the agent per task, and each
new task opens its own worktree. Agent selection + provider config is in the app's Providers screen — it
uses the operator's already-configured CLIs, so the lab's $0 gateway routing applies unchanged.

**Verified 2026-09-10 (eyes-on):** installed the v1.2.4 `.deb` on rogueone, added the weyland project,
created a task → Emdash opened a git worktree and drove a live Claude Code agent inside it. Working.

## Trap — the npm `emdash` name collision

`npm view emdash` / `npx emdash` resolves to an **unrelated Astro CMS** (`emdash-cms`, "Astro-native CMS
with WordPress migration") — NOT this supervisor. Do not `npx emdash`. The agent Emdash is the desktop
app from `releases.emdash.sh` / `generalaction/emdash` above. (Verified 2026-09-10.)

## Why this is a runbook, not a deployed service

Emdash is an operator-facing desktop UI run on a workstation (eyes-on, [[feedback-uat-eyes-on-ui]]); it is
not a LAN service to Argo-deploy, and making it a cluster app would trip the app-registry/doc-count guards
for no operational gain. Adopt on-demand; there is nothing here to keep running.

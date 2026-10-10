# Software-factory trials — Emdash · Vibe Kanban · OpenHands (B179)

Setup and run commands for the B179 experiments: can a free tool take a READY issue to a reviewable PR with nobody
steering? The verdict and the trial table live in [concepts/software-factory.md](../concepts/software-factory.md).
Everything here runs on **rogueone**, in user space; nothing is installed system-wide and the lab repo is touched only
through each trial's own worktree.

| Tool | Pinned version (2026-10-09) | Licence | Drives |
|---|---|---|---|
| Emdash | v1.2.7 (2026-09-27), x86_64 AppImage | Apache-2.0 | Claude Code / Codex / OpenCode CLIs (subscriptions, $0) |
| Vibe Kanban | 0.1.44 (2026-04-24; the project is sunsetting) | Apache-2.0 | the same CLIs |
| OpenHands CLI | `openhands` 1.16.0 on PyPI (Python 3.12) | MIT core | a model API — **local model only** in this trial ($0) |

## Install

Each command runs on rogueone. They download third-party executables, so the owner runs them.

**Emdash** (AppImage into `~/Applications`, no root):

[rogueone]
```
mkdir -p /home/edwardmangini/Applications && curl -fL -o /home/edwardmangini/Applications/emdash-1.2.7-x86_64.AppImage https://github.com/generalaction/emdash/releases/download/v1.2.7/emdash-x86_64.AppImage && chmod +x /home/edwardmangini/Applications/emdash-1.2.7-x86_64.AppImage && sha256sum /home/edwardmangini/Applications/emdash-1.2.7-x86_64.AppImage
```

**Vibe Kanban** (pre-fetch the pinned npm package; nothing global). `npx vibe-kanban@0.1.44` later STARTS the board
(a local web UI), so the install step only fetches it:

[rogueone]
```
npm cache add vibe-kanban@0.1.44
```

**OpenHands CLI** (pinned, run through `uvx`, isolated from the system Python):

[rogueone]
```
uvx --python 3.12 --from openhands==1.16.0 openhands --help
```

## Prerequisites the trials rely on

- Claude Code, Codex and OpenCode are already logged in on rogueone (subscriptions). Emdash and Vibe Kanban call these
  CLIs; they need no API key.
- Each trial works in its own git worktree of the lab repo, created by the tool. **No trial pushes or opens a PR without
  the owner's say-so** (the owner handles git); "reached a PR" is measured as a reviewable branch ready to push.
- OpenHands' local-model arm needs the operator's model unloaded first and restored afterwards (B179 edge cases).

## Running the trial

**The task, the same for every tool: B204 / [EMA-291](https://linear.app/emangini/issue/EMA-291)** — make
`register_bifrost_skills.py` publish a new version when a skill's content changed. Give each tool exactly the issue,
nothing more; a run that needs a nudge records where it needed it, and the nudge ends the "unattended" part.

1. **Emdash** — start it (`/home/edwardmangini/Applications/emdash-1.2.7-x86_64.AppImage`), open the lab repo
   (`/home/edwardmangini/IdeaProjects/weyland`), connect Linear, send EMA-291 to the **Claude Code** agent. Note the
   start time.
2. **Vibe Kanban** — start it in the lab repo (`npx vibe-kanban@0.1.44` from `/home/edwardmangini/IdeaProjects/weyland`;
   it opens a local board), create a card with EMA-291's text, assign **Claude Code**, start it.
3. **OpenHands** (local-model arm, last) — scheduled separately: it needs the operator's model unloaded and a local
   coding model chosen; the command goes here once that arm is set up.

Each run ends at a branch in its own worktree. Tell the agent session (or me) when a run stops; I then check the branch:
the diff, the tests (`run-lang-tests.sh python` on the Dagster scripts project), whether it met EMA-291's six acceptance
criteria, and the subscription usage. Nothing is pushed until you decide which branch, if any, becomes the real fix.

## Recording a run

Per run, record in the concepts doc's trial table: reached a reviewable branch with no human step after the start (or
where it stopped), time to that point, subscription usage (Claude Code `/cost` or the session transcript via
`scripts/ai_session_feeder.py`), CI and review-bot results once pushed, rework needed, and setup effort.

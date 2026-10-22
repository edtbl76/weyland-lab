# Software-factory trials — Emdash · OpenHands (B179)

Setup and run commands for the B179 experiments (Vibe Kanban was removed 2026-10-09 — dead, already rejected in B104): can a free tool take a READY issue to a reviewable PR with nobody
steering? The verdict and the trial table live in [concepts/software-factory.md](../concepts/software-factory.md).
Everything here runs on **rogueone**, in user space; nothing is installed system-wide and the lab repo is touched only
through each trial's own worktree.

| Tool | Pinned version (2026-10-09) | Licence | Drives |
|---|---|---|---|
| Emdash | v1.2.7 (2026-09-27), x86_64 AppImage | Apache-2.0 | Claude Code / Codex / OpenCode CLIs (subscriptions, $0) |
| OpenHands CLI | `openhands` 1.16.0 on PyPI (Python 3.12) | MIT core | a model API — **local model only** in this trial ($0). **Torn down 2026-10-12** after run 5 (`uv tool uninstall openhands`, trial image deleted, inventory pruned). The 32K model build `qwen3-coder:30b-32k` is kept: it is only a tag over the base model's blobs |

## Install

Each command runs on rogueone. They download third-party executables, so the owner runs them.

**Emdash** (AppImage into `~/Applications`, no root; the `.deb` route and the npm name-collision trap are in
[parallel-agent-supervisor.md](parallel-agent-supervisor.md) — B104):

**Launcher (2026-10-12):** on its first launch, AppImageLauncher integrated the download: it moved the file to
`~/Applications/emdash-x86_64_8287683f3c1e9ea3c7de9f556bb0ce0e.AppImage` and relaunched from there. Launch that file, or
the desktop menu entry; the `emdash-1.2.7-x86_64.AppImage` name below no longer exists. Keep ONE copy: the integration
relaunch killed an automation run that the first instance had started.

[rogueone]
```
mkdir -p /home/edwardmangini/Applications && curl -fL -o /home/edwardmangini/Applications/emdash-1.2.7-x86_64.AppImage https://github.com/generalaction/emdash/releases/download/v1.2.7/emdash-x86_64.AppImage && chmod +x /home/edwardmangini/Applications/emdash-1.2.7-x86_64.AppImage && sha256sum /home/edwardmangini/Applications/emdash-1.2.7-x86_64.AppImage
```

**OpenHands CLI** (pinned, installed as a `uv` tool, isolated from the system Python). Use `uv tool install`, not
`uvx`: `uvx` only caches the package, so the machine inventory (B129) cannot see it, and an install the inventory cannot
see is the gap that left Emdash uncataloged until 2026-10-12:

[rogueone]
```
uv tool install --python 3.12 openhands==1.16.0 && openhands --help
```

Then refresh the inventory so it lands in Port (`docs/runbooks/machine-inventory.md`).

## Prerequisites the trials rely on

- Claude Code, Codex and OpenCode are already logged in on rogueone (subscriptions). Emdash calls these CLIs; it needs no API key.
- Each trial works in its own git worktree of the lab repo, created by the tool. **No trial pushes or opens a PR without
  the owner's say-so** (the owner handles git); "reached a PR" is measured as a reviewable branch ready to push.
- OpenHands' local-model arm needs the operator's model unloaded first and restored afterwards (B179 edge cases).

## Running the trial

**The task, the same for every tool: B204 / [EMA-291](https://linear.app/emangini/issue/EMA-291)** — make
`register_bifrost_skills.py` publish a new version when a skill's content changed. Give each tool exactly the issue,
nothing more; a run that needs a nudge records where it needed it, and the nudge ends the "unattended" part.

1. **Emdash** — start it (`/home/edwardmangini/Applications/emdash-x86_64_8287683f3c1e9ea3c7de9f556bb0ce0e.AppImage`), open the lab repo
   (`/home/edwardmangini/IdeaProjects/weyland`), connect Linear, send EMA-291 to the **Claude Code** agent. Note the
   start time.
2. **OpenHands** (local-model arm, RUN 2026-10-12 as run 5; result in the concepts doc). Headless OpenHands always
   auto-approves, so it runs in a container with only a scratch copy of the repo mounted; its model is the 32K build
   `qwen3-coder:30b-32k` (`nodes/rogueone/ollama/qwen3-coder-30b-32k.Modelfile`). Loading it evicts the operator's
   model; reload that afterwards (step d). On rogueone:
   - a. Image (`python:3.12-bookworm` + `uv pip install --system openhands==1.16.0`), built as `b179-openhands:1.16.0`.
   - b. Scratch repo at the task's base: `git archive <base> | tar -x -C <dir>/work`, then `git init` + one commit
     there, so the diff is measurable and the real checkout is never touched.
   - c. **Saved settings, not env vars.** OpenHands sends `reasoning_effort=high` to every model, and Ollama answers
     `does not support thinking`; the `LLM_*` env overrides cannot unset it. Save the agent once with it unset:
     `LLM(model='openai/qwen3-coder:30b-32k', base_url='http://192.168.1.230:11434/v1', api_key='local-llm',
     reasoning_effort=None, usage_id='agent')` → `AgentStore().save(get_default_cli_agent(llm))`, with `HOME` = the
     mounted settings dir.
   - d. Run: `docker run --rm --user "$(id -u):$(id -g)" -e HOME=/home/oh -v <dir>/home:/home/oh -v <dir>/work:/work
     -v <task.md>:/task.md:ro -w /work b179-openhands:1.16.0 openhands --headless --json -f /task.md > run.jsonl`.
     **Do not trust its exit code**: it exited 0 after a fatal model error. Grade the diff and the JSONL events.
   - e. Afterwards: unload the coding model (`/api/generate` with `"keep_alive": 0`) and warm `qwen2.5:7b-operator`
     again.

Each run ends at a branch in its own worktree. Tell the agent session (or me) when a run stops; I then check the branch:
the diff, the tests (`run-lang-tests.sh python` on the Dagster scripts project), whether it met EMA-291's six acceptance
criteria, and the subscription usage. Nothing is pushed until you decide which branch, if any, becomes the real fix.

## The conveyor: `agent-ready-nightly` (ADOPTED 2026-10-12)

The definition of record. Emdash keeps it in its own database (backed up by rogueone's restic, which includes
`~/.config`); this section is the copy in git, so it can be rebuilt by hand in **Settings → Automations** if that is lost.

| Field | Value |
|---|---|
| Name | `agent-ready-nightly` |
| Project | `weyland` (`/home/edwardmangini/IdeaProjects/weyland`, remote `edtbl76/weyland-lab`) |
| Schedule | `0 4 * * *`, `America/New_York` (04:00 NY) |
| Agent | Claude Code (TUI), auto-approve ON |
| Workspace | new worktree, new branch from `origin/main`, **push OFF** (`pushBranch: false` → `pushRemote: null`) |

Prompt, verbatim:

```
Using the Linear MCP, find the oldest open issue in the Weyland Lab project that carries the label agent-ready. If there is none, stop and say so.
Check it is ready: run /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh <ISSUE-ID> --no-comment from /home/edwardmangini/IdeaProjects/weyland (it reads LINEAR_API_KEY from scripts/.env there). If it does not print READY, stop and say why.
Implement the issue in this worktree, following its acceptance criteria and the repo's AGENTS.md. Run the tests the issue names and report each acceptance criterion as met or not met, with evidence.
Leave your changes uncommitted in this worktree. Do not commit, push, open a pull request, or change anything in the cluster.
```

**Using it:** make an issue READY (`scripts/issue-readiness.sh EMA-###`), add the Linear label `agent-ready`, and leave
Emdash running. The next 04:00 run, or the next launch if the slot was missed, takes the oldest labelled issue. In the
morning, read the run's transcript (`~/.claude/projects/*emdash-<run>*/*.jsonl`) and its worktree
(`~/emdash/worktrees/weyland-93040a9c/emdash-<run>`). Bring the change into `main` if it is good, then **remove the
`agent-ready` label** (otherwise the next run redoes it) and clear the worktree:
`git worktree remove <path> && git branch -D emdash-<run>`.

## Worktree sweep — `emdash-worktree-sweep` (B179, 2026-10-22)

Every run opens a worktree and an `emdash-<run>` branch, even on a night with no `agent-ready` issue, and nothing removed
them: 10 had piled up by 2026-10-22, all empty. A daily user timer (06:30 NY, after the 04:00 run and the 06:00 watch)
removes a run worktree and its branch only when it has **no uncommitted or untracked change**, **no commit that is not on
`origin/main`**, and is **older than 24 h** (so a run in progress is never touched). Anything with work in it is kept and
named in the journal: review those by hand, as above. Only worktrees under `~/emdash/worktrees` on an `emdash-` branch are
considered (decision flow: [flow-emdash-worktree-sweep.md](../diagrams/flow-emdash-worktree-sweep.md)). Logic `scripts/emdash-worktree-sweep.sh` (8 bats against real git repos), units
`nodes/rogueone/systemd/emdash-worktree-sweep.{service,timer}`.

See what it would do (removes nothing):

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/emdash-worktree-sweep.sh
```
2026-10-22: `would remove` 8 empty worktrees (79 to 237 h old), 2 kept as younger than 24 h.

Before the first timed run, prove Emdash tolerates a worktree disappearing (it keeps its own record of each run): remove
the oldest by hand, then open Emdash, check the run list still shows and the automation is still enabled.

[rogueone]
```
git -C /home/edwardmangini/IdeaProjects/weyland worktree remove /home/edwardmangini/emdash/worktrees/weyland-93040a9c/emdash-da39df5f && git -C /home/edwardmangini/IdeaProjects/weyland branch -D emdash-da39df5f
```
Then install the timer (and see the journal after the first run):

[rogueone]
```
cp /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/emdash-worktree-sweep.service /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/emdash-worktree-sweep.timer /home/edwardmangini/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now emdash-worktree-sweep.timer && systemctl --user start emdash-worktree-sweep.service && journalctl --user -u emdash-worktree-sweep -n 20 --no-pager
```

## Freshness — `emdash-conveyor-watch` (B179 DoD)

The conveyor fails by silence (no app, no run), so a daily check at 06:00 NY reads Emdash's run records, read-only,
and reports to an Uptime-Kuma **push** monitor: **up** if `agent-ready-nightly` started a run in the last 26 h; **down**
if none did (is Emdash running?), if the automation is disabled, or if the store cannot be read. Exit codes: 0 / 1 / 2.
The monitor's own heartbeat timeout catches a watch that stops running.

**Set up once (owner):**
1. In Kuma, add a monitor of type **Push**, named `emdash-conveyor`, heartbeat interval **90000 s** (25 h), with the
   lab's Telegram notification. Copy its push URL.
2. Add it to `scripts/.env` as `KUMA_CONVEYOR_PUSH_URL=<the push URL>` (it is a credential: never paste it in chat).
3. Install and start the timer:

[rogueone]
```
cp /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/emdash-conveyor-watch.{service,timer} ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now emdash-conveyor-watch.timer && systemctl --user start emdash-conveyor-watch.service && journalctl --user -u emdash-conveyor-watch -n 3 --no-pager -o cat
```

Expected: `emdash-conveyor-watch: exit 0 — last run started N h ago`, and the Kuma monitor turns green.

## Start at login — XDG autostart (B179 DoD re-audit, 2026-10-21)

The conveyor runs only while Emdash is open, and nothing started it after a reboot: rogueone rebooted 2026-10-19 09:28,
no run fired for two nights, and the watch above went **down** on 10-20 06:00. The fix is an XDG autostart entry that
starts Emdash 30 s into every login of the owner's desktop session. The source of record is
`nodes/rogueone/autostart/emdash.desktop`; `placement.yaml` tracks the installed copy as a `host_config` row, so a
missing or edited copy shows up in the placement-coverage check. Install or reinstall it:

[rogueone]
```
cp /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/autostart/emdash.desktop /home/edwardmangini/.config/autostart/emdash.desktop && desktop-file-validate /home/edwardmangini/.config/autostart/emdash.desktop && cmp /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/autostart/emdash.desktop /home/edwardmangini/.config/autostart/emdash.desktop && echo installed
```

Expected: `installed`, with no validator output. **After a reboot** (or the first install), confirm Emdash is up; if
it is not, launch it from the desktop menu. A missed 04:00 slot runs seconds after the launch only while it is within
its 24 h deadline (§ Emdash automation settings, Scheduling):

[rogueone]
```
pgrep -fa emdash-x86_64 | head -3
```

**If the AppImage is replaced** (a new Emdash version gets a new file name from AppImageLauncher), update `Exec=` and
`TryExec=` in the source file and reinstall. `TryExec` points at the old file, so a stale entry is silently skipped at
login rather than failing loudly; the watch above is what catches it.

## Emdash automation settings

An automation lives in two places:
- **The template:** `~/.config/emdash/emdash4.db`, table `automations`, column `task_config` (JSON).
  `workspaceConfig.git.pushBranch` decides whether each run publishes its task branch to GitHub. It is **false** for
  `agent-ready-nightly` since 2026-10-12; before that it pushed an empty branch every night.
- **The compiled deployment the scheduler actually runs:** `emdash4-automations.db`, `automation_deployments.payload`,
  where push is `workspace.git.pushRemote`. The app rebuilds it from the template on launch.

**How to change it:** the app's UI has no push option, so edit the template, with Emdash fully quit and after a backup
(`sqlite3` `.backup`, then `pragma integrity_check`). **Never delete `pushRemote`:** Emdash validates it and refuses to boot
without it (`expected string, received undefined`). No-push is `null`.

**Scheduling, measured 2026-10-12:** a run cannot fire while Emdash is closed. Its scheduler lives in the app, with no
daemon, unit, timer or cron. A missed run keeps a 24 h deadline and starts by itself seconds after the next launch. So the
nightly queue needs Emdash running on rogueone; otherwise it runs whenever the app is next opened. **Only within that
deadline (measured 2026-10-21):** the scheduler holds ONE pending slot (`automation_runs.status = scheduled`). Launched
after its `deadline_at`, that slot is marked `skipped`, the slots that fell while the app was down are never created, and
the next run is the next future 04:00. So after two nights down, a launch runs nothing until the following morning;
check that the scheduler is armed (a `scheduled` row), and **prove the conveyor now with a manual run** instead of
waiting: in Emdash, **Automations → `agent-ready-nightly` → Runs tab → the ▶ icon at the right of the tab row**
(tooltip "Run now"; greyed out with a reason when it cannot run). It records `triggerKind: manual` with no deadline,
and `systemctl --user start emdash-conveyor-watch.service` then reports `exit 0`. If the window is closed, Emdash is
still in the tray; launching the AppImage again raises the running instance (it does not start a second one).
Read-only:
`python3 -c "import sqlite3,os;c=sqlite3.connect('file:'+os.path.expanduser('~/.config/emdash/emdash4-automations.db')+'?mode=ro',uri=True);print(c.execute(\"select seq,status,datetime(scheduled_at/1000,'unixepoch') from automation_runs order by seq desc limit 3\").fetchall())"`.
The launch log line `Failed to deploy an automation definition … no git remotes` is harmless: Emdash's `project_remotes`
is empty, so it cannot RE-deploy the template, but the compiled deployment (which names `origin`) keeps running — it has
logged that on every launch since 2026-10-12 and every night ran. Emdash ignores SIGTERM
(it stays in the tray); a run's `done` status means dispatched, not finished, so grade from its transcript.

## Recording a run

Per run, record in the concepts doc's trial table: reached a reviewable branch with no human step after the start (or
where it stopped), time to that point, subscription usage (Claude Code `/cost` or the session transcript via
`scripts/ai_session_feeder.py`), CI and review-bot results once pushed, rework needed, and setup effort. A run's agent
time and tokens per issue come from the issue-time report ([issue-time.md](issue-time.md)): a conveyor run is attributed
by its `issue-readiness.sh EMA-###` call.

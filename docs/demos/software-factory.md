# Demo — the software-factory conveyor (B179)

**What it shows:** a READY Linear issue labelled `agent-ready` is picked up by the Emdash automation
`agent-ready-nightly` at 04:00 (or on the next launch if the slot was missed), implemented by Claude Code in a fresh local
worktree, and left for a person to review. Nothing is committed or pushed. Verdicts and the trial evidence:
[concepts/software-factory.md](../concepts/software-factory.md); setup: [runbooks/software-factory.md](../runbooks/software-factory.md);
flow: [diagrams/flow-emdash-parallel-agents.md](../diagrams/flow-emdash-parallel-agents.md).

## UI walkthrough (UAT)

1. Open Emdash (the desktop menu entry, or
   `/home/edwardmangini/Applications/emdash-x86_64_8287683f3c1e9ea3c7de9f556bb0ce0e.AppImage`). **Confirm:** it opens on the
   `weyland` project (`edtbl76/weyland-lab`) with no error.
2. Open **Automations** → `agent-ready-nightly`. **Confirm:** schedule "At 04:00 AM", the `weyland` project, and the next
   run listed for the coming 04:00.
3. In Linear, open the label `agent-ready` (team EMA). **Confirm:** it exists, and only issues you have released carry it.
4. The morning after a run: open the run's worktree in Emdash (or your editor). **Confirm:** the changes are uncommitted
   and nothing new appears under GitHub branches.

## CLI walkthrough (RUN 2026-10-12)

The run records, from Emdash's own database (read-only):

[rogueone]
```
python3 -c "import sqlite3,json,datetime; c=sqlite3.connect('file:/home/edwardmangini/.config/emdash/emdash4-automations.db?mode=ro',uri=True); [print(r[0], r[1], datetime.datetime.fromtimestamp((json.loads(r[2]).get('startedAt') or 0)/1000), json.loads(r[2]).get('branchName')) for r in c.execute('select seq,status,payload from automation_runs order by seq desc limit 4')]"
```

Real output (the catch-up proof, 2026-10-12): `27 done 2026-10-12 14:08:40 emdash-da39df5f`. That run's slot was
13:59:25 with Emdash closed, and it started by itself at launch.

What the agent did, from its transcript:

[rogueone]
```
python3 -c "import json,glob; t=sorted(glob.glob('/home/edwardmangini/.claude/projects/*emdash-da39df5f*/*.jsonl'))[-1]; [print(x['name']) for l in open(t) for x in (json.loads(l).get('message') or {}).get('content') or [] if isinstance(x,dict) and x.get('type')=='tool_use']"
```

Real output: `ToolSearch`, `mcp__linear__list_issues`, `mcp__linear__list_issue_labels`, `mcp__linear__list_issues`,
`mcp__linear__list_issues`, then "There are no issues labelled `agent-ready` in the Weyland Lab project, so I've stopped".
It checked that the label and the project filter are valid before saying none.

Nothing was pushed (push is off):

[rogueone]
```
git -C /home/edwardmangini/IdeaProjects/weyland ls-remote origin 'refs/heads/emdash-*'
```

Real output: empty.

**With work in the queue** (runs 1 to 3, 2026-10-09/10): each run met every acceptance criterion in 7 to 9 minutes. Run 3
found EMA-292 by the label alone and also reported two defects the spec had missed. The trial table holds the evidence.

**Negative case, the OpenHands arm (run 5):** on a local model the same task took 77 minutes, wrote no tests and rewrote
skill content while reporting success. That is why it is DON'T ADOPT. It ran only in a sandbox copy.

## Teardown

Read-only. An empty-queue run creates one local worktree and branch, `emdash-<run>`; clear it with
`git worktree remove <path> && git branch -D emdash-<run>`.

# Demo: several coding agents side by side in Herdr (B257)

Two agents in parallel, their states, a blocked prompt, a hand-off, and a dropped client. Flow:
[flow-herdr-multi-agent](../diagrams/flow-herdr-multi-agent.md); runbook: [herdr.md](../runbooks/herdr.md). Run live on
rogueone on 2026-11-22 (the B257 trial; outputs below are from that run). It uses a named session so it never touches
your default one. It creates only that session's state: the teardown at the end removes it.

## CLI walkthrough

[rogueone]
```
herdr --session demo server
```

In a second terminal: a workspace in the repo, a second pane, and an agent in each.

[rogueone]
```
herdr --session demo workspace create --cwd /home/edwardmangini/IdeaProjects/weyland --label demo && herdr --session demo pane split --pane w1:p1 --direction right --cwd /home/edwardmangini/IdeaProjects/weyland --no-focus
```

[rogueone]
```
herdr --session demo agent start claude1 --kind claude --pane w1:p1 && herdr --session demo agent start codex1 --kind codex --pane w1:p2
```

Expected: two JSON results with `"agent_status":"idle"`. If Codex opens with a question, read it first
(`herdr --session demo agent read codex1`): Herdr shows that start-up question as `idle`.

Prompt both with read-only tasks, then watch their states:

[rogueone]
```
herdr --session demo agent prompt claude1 "Read docs/adr/0006-vibe-kanban-is-out.md and summarise it in 3 bullets. Do not edit files." && herdr --session demo agent prompt codex1 "Read docs/concepts/multi-harness.md and list the harnesses. Do not edit files." && herdr --session demo agent list
```

Expected (2026-11-22): `claude1=working codex1=working`, then both `idle` about 20 seconds later; `herdr --session demo
agent read <name>` shows each answer.

**Blocked:** ask either agent to write a file outside the repo; its permission prompt shows as `blocked` within about 4
seconds (`agent list`), and `agent explain <name>` names the rule (`bash_permission_prompt` for Claude Code,
`osc_title_blocked` for Codex). Answer "No" (`herdr --session demo agent send-keys claude1 esc`).

**Hand-off** from a shell pane inside the session (`HERDR_ENV=1` there):

[rogueone]
```
herdr --session demo agent prompt codex1 "Count the files matching docs/adr/0*.md and reply with just the number." --wait --timeout 180000; echo exit=$?
```

Expected: `exit=0` when Codex finishes, and its pane shows the count (17 on 2026-11-22).

## UI walkthrough (UAT, eyes on)

Attach the TUI: `herdr --session demo`. Confirm: the sidebar lists workspace `demo` with two agents; each pane shows its
agent; a prompted agent's badge turns to working, then idle; a permission prompt turns its pane, tab and workspace to
blocked. Detach with `ctrl+b q`, run `herdr --session demo agent list`: both agents are still listed and running. Close
the terminal window instead of detaching, reattach, and confirm the same.

## Teardown

[rogueone]
```
herdr --session demo server stop && rm -r /home/edwardmangini/.config/herdr/sessions/demo
```

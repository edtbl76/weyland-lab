"""Print a trial's top-level flow as an ordered list of steps: skills invoked, sub-agents spawned, files written or
edited, and test/engine commands, collapsing consecutive reads. usage: run_flow.py <run.jsonl>"""
import json
import re
import sys

steps = []


def add(kind, text):
    if steps and steps[-1][0] == kind == "read":
        steps[-1] = (kind, steps[-1][1] + 1)
        return
    steps.append((kind, text))


for line in open(sys.argv[1]):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if not isinstance(e, dict) or e.get("type") != "assistant" or e.get("parent_tool_use_id"):
        continue
    for c in (e.get("message") or {}).get("content") or []:
        if not isinstance(c, dict) or c.get("type") != "tool_use":
            continue
        n, i = c.get("name"), c.get("input") or {}
        if n == "Skill":
            add("skill", i.get("skill") or i.get("command") or "?")
        elif n in ("Task", "Agent"):
            add("agent", (i.get("description") or i.get("subagent_type") or "?")[:60])
        elif n in ("Write", "Edit"):
            add(n.lower(), re.sub(r"^.*/trials/[^/]+/", "", i.get("file_path", "?")))
        elif n == "Bash":
            cmd = i.get("command", "")
            if re.search(r"\b(bats|pytest|promtool|uv run|render_skill|openspec|bun )", cmd):
                add("run", cmd.split("\n")[0][:90])
            else:
                add("read", 1)
        elif n in ("Read", "Glob", "Grep"):
            add("read", 1)
for k, t in steps:
    print(f"  {k:6} {t if k != 'read' else str(t) + ' read/search call(s)'}")

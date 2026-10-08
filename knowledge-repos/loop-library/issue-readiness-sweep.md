---
id: issue-readiness-sweep
title: The issue readiness sweep
category: Engineering
description: Bring every open High issue in Weyland Lab up to the implementation-ready standard so any of them can be handed to an agent.
terminal_condition: The sweep prints READY for every open High issue in project Weyland Lab, or an issue needs a decision only the owner can make (stop and list those issues).
source: docs/runbooks/issue-readiness.md (Check an issue; The standard)
---

## Prompt

Make every open High issue in Linear project Weyland Lab implementation-ready.

1. Run the sweep from `docs/runbooks/issue-readiness.md` (`bash scripts/issue-readiness.sh --sweep --no-comment`).
   Read every `missing:` line.
2. For each NOT READY issue, read the issue and its `docs/backlog.md` entry, then write the missing sections from
   the issue's kind (Backlog item, Bug, Spike or Bucket; the table in the runbook). Use real facts from the repo:
   paths, hosts, services, commands. Never invent a fact; where a fact is unknown, write that it is unknown.
3. Keep every existing word the issue already has; add, do not rewrite. Acceptance criteria must be checkable
   pass/fail items.
4. Re-run the check on that issue. It must print READY before you move on.

Stop when the terminal condition holds. Report the issues changed and any that need the owner, with the question
each one needs answered.

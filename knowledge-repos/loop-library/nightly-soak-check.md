---
id: nightly-soak-check
title: The nightly soak check
category: Operations
description: Each morning, check last night against a soak's written acceptance query, record the result, and close the item when the clean-night target is reached.
terminal_condition: The soak reaches its target count of consecutive clean nights (record it and close the item), or a night fails its check (record the failure with the evidence and stop for the owner).
pacing: Once a day, after the night window has ended. Never more often.
source: docs/runbooks/node-capacity.md (Night check, B199), docs/runbooks/woodpecker.md (Soak check, B201)
---

## Prompt

Check last night for the soak on {{item}}.

1. Open the item's written acceptance check in its runbook (for example `docs/runbooks/node-capacity.md` Night check
   for B199, `docs/runbooks/woodpecker.md` Soak check for B201). Run it exactly as written, in Grafana Explore or
   through the Grafana MCP, over last night's window.
2. Run the control the runbook names too (an unfiltered query, or a known positive window). A query that returns
   nothing proves nothing until the control shows the data source works.
3. Decide clean or failed against the runbook's thresholds. Do not reinterpret a threshold.
4. Record the night in the item in `docs/backlog.md` and as a comment on its Linear issue: the date, the numbers,
   and the running count (for example "night 6 of 7 clean").

Stop when the terminal condition holds. On the final clean night, also do the item's close-out step (for B201, drop
the temporary rule its runbook names). On a failed night, stop and report the evidence; do not restart the count
without the owner.

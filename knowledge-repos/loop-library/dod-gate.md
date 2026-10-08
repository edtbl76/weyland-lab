---
id: dod-gate
title: The Definition of Done gate
category: Engineering
description: Grade a finished backlog item against the 9-pillar Definition of Done, close every gap found, and only then mark it DONE in the backlog and Linear.
terminal_condition: Every one of the 9 pillars carries evidence or a one-line N/A with its reason, the backlog item and its Linear issue both say DONE, and scripts/check-linear-sync.sh exits 0; or a pillar needs a decision only the owner can make (stop and ask).
source: docs/definition-of-done.md, scripts/check-linear-sync.sh
---

## Prompt

The owner said "DoD" for backlog item {{item}}. Grade it against `docs/definition-of-done.md` and close every gap.

For each pillar in order (1 Docs, 2 Diagrams, 3 Demos, 4 Cleanup, 5 Tracking, 6 Ops, 7 Scan, 8 Cascade, 9 DR):
1. Read the pillar's rules in `docs/definition-of-done.md`. For repo tooling, use its "Applying this to REPO TOOLING"
   table.
2. Find the evidence: a file path, a command and its output, a guard's exit code. An unasked question and an empty
   answer look identical, so look, do not assume.
3. If the pillar has a gap, close it now (fix, don't file), then re-check. If it genuinely does not apply, write a
   one-line N/A with the reason.

Then run the full local guard suite and `scripts/check-linear-sync.sh`. Write the DONE paragraph into the item in
`docs/backlog.md` (one line per pillar, evidence named), flip its list entry to DONE with the date, and set the
Linear issue to Done with a comment.

Stop when the terminal condition holds. If a pillar needs an owner decision (a cost, a hardware dependency, a
deferral), stop and ask one question with your recommendation; do not mark the item DONE.
